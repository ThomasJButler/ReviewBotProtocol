from services.redaction import is_excluded_path, redact


def test_api_tokens_are_masked():
    text = ("+OPENAI_API_KEY = 'sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGH'\n"
            "+token = 'ghp_" + "a" * 36 + "'\n"
            "+pat = 'github_pat_" + "b" * 30 + "'\n"
            "+aws = AKIAABCDEFGHIJKLMNOP\n"
            "+g = 'AIza" + "c" * 35 + "'\n"
            "+//registry.npmjs.org/:_authToken=npm_" + "d" * 36 + "\n"
            "+SLACK_APP=xapp-1-A0123456789-" + "e" * 20 + "\n"
            "+conn = 'DefaultEndpointsProtocol=https;AccountName=x;AccountKey=" + "f" * 60 + "=='\n")
    out, counts = redact(text)
    for leaked in ("sk-proj-abcdef", "ghp_aaaa", "github_pat_bbb", "AKIAABCDEFGHIJKLMNOP", "AIzaccc", "npm_dddd", "xapp-1-A0123456789-eeee", "ffffffffff"):
        assert leaked not in out, leaked
    assert counts["openai-key"] == 1 and counts["github-token"] == 2 and counts["npm-token"] == 1
    assert counts["slack-token"] == 1 and counts["azure-key"] == 1
    assert out.count("\n") == text.count("\n")


def test_private_key_block_is_masked_line_by_line():
    text = "@@ -1,5 +1,6 @@\n import os\n+-----BEGIN RSA PRIVATE KEY-----\n+MIIEpAIBAAKCAQEA1234abcdefghijkl\n+abcdefghijklmnopqrstuvwxyz0123456789\n+-----END RSA PRIVATE KEY-----\n+after = 1\n"
    out, counts = redact(text)
    assert "MIIEpAIBAAKCAQEA1234" not in out and "abcdefghijklmnopqrstuvwxyz0123456789" not in out
    assert out.count("\n") == text.count("\n")
    lines = out.split("\n")
    assert lines[2] == "+[REDACTED:private-key]" and lines[3] == "+[REDACTED:private-key]" and lines[5] == "+[REDACTED:private-key]"
    assert lines[6] == "+after = 1" and lines[1] == " import os"
    assert counts["private-key"] == 1


def test_unterminated_private_key_does_not_swallow_the_rest_of_the_patch():
    text = "+-----BEGIN OPENSSH PRIVATE KEY-----\n+b3BlbnNzaC1rZXktdjEAAAAAAAAAAAAAAAAA\n+query = f\"SELECT * FROM users WHERE id = '{user_id}'\"\n@@ -10,2 +11,3 @@\n+more = 2\n"
    out, _ = redact(text)
    assert "b3BlbnNzaC1rZXktdjEAAAAA" not in out
    assert "SELECT * FROM users" in out and "@@ -10,2 +11,3 @@" in out and "+more = 2" in out
    assert out.count("\n") == text.count("\n")


def test_url_password_and_auth_header_are_masked():
    out, counts = redact("DATABASE_URL=postgres://app:S3cret@Pass@word@db:5432/x\nAuthorization: Bearer abcdefghijklmnop.123\n")
    assert "S3cret" not in out and "Pass@word" not in out and "@db:5432/x" in out
    assert "abcdefghijklmnop.123" not in out


def test_quoted_and_unquoted_assignments_are_masked_but_code_and_placeholders_kept():
    text = ("password = 'hunter2hunter2'\n"
            "SECRET_KEY: \"your-secret-key-here\"\n"
            "api_key = '${API_KEY}'\n"
            "DB_PASSWORD=Tr0ub4dor3xyzQ9\n"
            "token: ghx0123456789abcdef\n"
            "token = get_token(config)\n"
            "secret = example_loader()\n")
    out, counts = redact(text)
    assert "hunter2hunter2" not in out and "Tr0ub4dor3xyzQ9" not in out and "ghx0123456789abcdef" not in out
    assert "your-secret-key-here" in out and "${API_KEY}" in out
    assert "get_token(config)" in out and "example_loader()" in out
    assert counts.get("assigned-secret") == 3


def test_placeholder_hints_are_anchored_not_substring():
    out, _ = redact("password = 'realexamplepassword9'\napi_key = 'abc<def>ghi123456'\n")
    assert "realexamplepassword9" not in out and "abc<def>ghi123456" not in out


def test_short_sk_identifiers_are_not_redacted():
    text = "sk-dev-build-artifact-name = 1\n"
    assert redact(text)[0] == text


def test_clean_text_is_untouched():
    text = "def add(a, b):\n    return a + b\n"
    assert redact(text) == (text, {})


def test_excluded_paths():
    for p in [".env", ".env.production", "config/.env.local", "certs/server.pem", "id_rsa", "keys/id_ed25519",
              "infra/prod.tfvars", "terraform.tfstate", ".npmrc", "credentials.json", "service-account-prod.json",
              "kubeconfig", "secrets.yaml", "secret.yml", "vault.yaml", ".git-credentials", "store.jks", "svc.keytab"]:
        assert is_excluded_path(p), p
    for p in ["src/app.py", "README.md", "env.example", "keys.py", ".env.example", ".env.example.txt", "docs/pemberton.md"]:
        assert not is_excluded_path(p), p
