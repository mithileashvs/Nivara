import { Component } from 'react'
import { AlertTriangle } from 'lucide-react'

/** Last line of defence: a rendering bug shows a readable page, never a blank one. */
export class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error('Nivara UI error', error, info)
  }

  render() {
    if (!this.state.hasError) return this.props.children
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-canvas px-6 text-center">
        <span className="flex h-12 w-12 items-center justify-center rounded-full bg-danger-soft text-danger">
          <AlertTriangle size={22} aria-hidden="true" />
        </span>
        <h1 className="mt-4 text-xl font-semibold text-forest-700">This page stopped working</h1>
        <p className="mt-2 max-w-sm text-sm text-ink-muted">
          Reload to carry on. If it keeps happening, tell your Nivara administrator what you were
          doing.
        </p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="mt-8 inline-flex h-11 items-center rounded-xl bg-forest px-5 text-sm font-medium text-canvas transition-colors hover:bg-forest-700 focus-ring"
        >
          Reload the page
        </button>
      </div>
    )
  }
}
