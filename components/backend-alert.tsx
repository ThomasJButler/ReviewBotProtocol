import { TriangleAlert } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { backendUrl, type ApiFailure } from '@/lib/api'

const TITLES: Record<ApiFailure['kind'], string> = {
  config: 'The dashboard has no backend token',
  unreachable: 'The backend is not answering',
  auth: 'The backend rejected the local token',
  http: 'The backend returned an error',
}

/**
 * Shown instead of a crash whenever a page cannot read the backend. It names
 * the two environment variables the operator has to set.
 */
export function BackendAlert({ failure }: { failure: ApiFailure }) {
  return (
    <Alert variant="destructive">
      <TriangleAlert aria-hidden="true" />
      <AlertTitle>{TITLES[failure.kind]}</AlertTitle>
      <AlertDescription>
        <p>{failure.message}</p>
        <p>
          Set <code className="font-mono">BACKEND_URL</code> (currently{' '}
          <code className="font-mono">{backendUrl()}</code>) and{' '}
          <code className="font-mono">LOCAL_API_TOKEN</code> in{' '}
          <code className="font-mono">.env.local</code>, then start the backend
          with <code className="font-mono">uvicorn main:app --port 8000</code>{' '}
          and reload this page.
        </p>
      </AlertDescription>
    </Alert>
  )
}
