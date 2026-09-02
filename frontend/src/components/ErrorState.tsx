type ErrorStateProps = {
  onRetry: () => void
}

function ErrorState({ onRetry }: ErrorStateProps) {
  return (
    <main className="state-screen" aria-live="polite">
      <section className="state-panel">
        <p className="state-panel__label">Market data unavailable</p>
        <h1>Unable to load the market dashboard.</h1>
        <p>The sample market service could not be reached. Please try again.</p>
        <button className="retry-button" type="button" onClick={onRetry}>
          Retry request
        </button>
      </section>
    </main>
  )
}

export default ErrorState
