import { CopySnippet } from '@/components/copy-snippet'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

export const metadata = { title: 'Setup' }

const PERMISSIONS = [
  { name: 'Pull requests', access: 'Read and write' },
  { name: 'Metadata', access: 'Read' },
]

export default function SetupPage() {
  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">Setup</h1>
        <p className="max-w-prose text-muted-foreground">
          Five steps from an empty machine to a reviewed pull request. Every
          step runs on your own hardware; no inference key is involved. The
          optional hosted mode for a bigger model is in
          docs/HOSTED_MODEL_PLAN.md.
        </p>
      </div>

      <ol className="space-y-6">
        <li>
          <Card>
            <CardHeader>
              <CardTitle>1. Install Ollama and pull the model</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <p>
                Install Ollama from ollama.com, then pull the model the backend
                is configured to use.
              </p>
              <CopySnippet
                text="ollama pull qwen3.5:9b"
                label="the model pull command"
              />
              <p className="text-muted-foreground">
                Check it answers before going further.
              </p>
              <CopySnippet
                text="curl -s http://127.0.0.1:11434/api/tags"
                label="the Ollama check command"
              />
            </CardContent>
          </Card>
        </li>

        <li>
          <Card>
            <CardHeader>
              <CardTitle>2. Create the GitHub App</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <p>
                Create the App under your account or organisation settings, at
                Developer settings, GitHub Apps, New GitHub App.
              </p>
              <ul className="list-disc space-y-1 pl-5">
                <li>
                  Name: anything you like, for example ReviewBot Protocol
                  (local).
                </li>
                <li>
                  Webhook URL: the public address of this backend plus{' '}
                  <code className="font-mono">/webhook/github</code>.
                </li>
                <li>
                  Webhook secret: generate one and keep it, you need it in step
                  3.
                </li>
                <li>
                  Private key: generate one at the bottom of the App page and
                  save the PEM next to the backend.
                </li>
                <li>Install on selected repositories, not all of them.</li>
              </ul>

              <CopySnippet
                text="openssl rand -hex 32"
                label="the webhook secret command"
              />

              <div className="overflow-x-auto rounded-lg border border-border">
                <Table>
                  <TableCaption className="px-4 pb-3 text-left">
                    The App needs exactly these permissions and nothing else.
                  </TableCaption>
                  <TableHeader>
                    <TableRow>
                      <TableHead scope="col">Permission</TableHead>
                      <TableHead scope="col">Access</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {PERMISSIONS.map(permission => (
                      <TableRow key={permission.name}>
                        <TableCell>{permission.name}</TableCell>
                        <TableCell>{permission.access}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              <p>
                Subscribe to one event only: <strong>Pull request</strong>.
                Leave every other event unticked.
              </p>
            </CardContent>
          </Card>
        </li>

        <li>
          <Card>
            <CardHeader>
              <CardTitle>3. Fill in the backend environment</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <p>
                Copy <code className="font-mono">backend/.env.example</code> to{' '}
                <code className="font-mono">backend/.env</code> and set the
                three GitHub values plus the dashboard token.
              </p>
              <CopySnippet
                text={`GITHUB_APP_ID=
GITHUB_PRIVATE_KEY=./github-app.pem
GITHUB_WEBHOOK_SECRET=
LOCAL_API_TOKEN=`}
                label="the backend environment block"
              />
              <p>
                Generate the dashboard token, then put the same value in the
                dashboard&rsquo;s own{' '}
                <code className="font-mono">.env.local</code> as{' '}
                <code className="font-mono">LOCAL_API_TOKEN</code> alongside{' '}
                <code className="font-mono">BACKEND_URL</code>. The dashboard
                reads both on the server; neither ever reaches the browser.
              </p>
              <CopySnippet
                text="openssl rand -hex 24"
                label="the dashboard token command"
              />
              <CopySnippet
                text={`BACKEND_URL=http://127.0.0.1:8000
LOCAL_API_TOKEN=`}
                label="the dashboard environment block"
              />
            </CardContent>
          </Card>
        </li>

        <li>
          <Card>
            <CardHeader>
              <CardTitle>4. Let GitHub reach the webhook</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <p>
                The backend listens on{' '}
                <code className="font-mono">127.0.0.1</code>. GitHub needs a
                route to it, either a tunnel or a reverse proxy you already run.
                Whichever you choose, add the public hostname to{' '}
                <code className="font-mono">ALLOWED_HOSTS</code> in{' '}
                <code className="font-mono">backend/.env</code>, or the request
                is refused before it is read.
              </p>
              <CopySnippet
                text="ALLOWED_HOSTS=localhost,127.0.0.1,your-tunnel-hostname"
                label="the allowed hosts line"
              />
              <p className="text-muted-foreground">
                Only the webhook route needs to be reachable. Keep the dashboard
                API on loopback: a tunnel that forwards the whole port also
                exposes it, behind the token alone. This dashboard has no login
                of its own either. It binds to 127.0.0.1 and refuses any other
                host name, and it must stay that way.
              </p>
            </CardContent>
          </Card>
        </li>

        <li>
          <Card>
            <CardHeader>
              <CardTitle>5. Verify</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <p>
                Start the backend, then open the App&rsquo;s Advanced tab on
                GitHub and redeliver the ping. It should appear under Recent
                deliveries on the Status page within a second or two.
              </p>
              <CopySnippet
                text="cd backend && .venv/bin/uvicorn main:app --port 8000"
                label="the backend start command"
              />
              <p>
                Then open a pull request on an installed repository. The review
                appears on the Reviews page while it runs.
              </p>
            </CardContent>
          </Card>
        </li>
      </ol>
    </div>
  )
}
