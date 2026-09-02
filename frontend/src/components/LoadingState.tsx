function LoadingState() {
  return (
    <main className="dashboard dashboard--loading" aria-live="polite" aria-busy="true">
      <div className="loading-header">
        <span className="loading-line loading-line--brand" />
        <span className="loading-line loading-line--meta" />
      </div>
      <section className="dashboard-content">
        <div className="loading-line loading-line--title" />
        <div className="metric-grid">
          {[1, 2, 3, 4].map((item) => (
            <div className="loading-card" key={item} />
          ))}
        </div>
        <div className="loading-table-grid">
          {[1, 2, 3].map((item) => (
            <div className="loading-table" key={item} />
          ))}
        </div>
      </section>
    </main>
  )
}

export default LoadingState
