import { useEffect, useState } from 'react'

import { getHealth, type HealthResponse } from './api/health'

type ConnectionState =
  | { status: 'checking' }
  | { status: 'connected'; health: HealthResponse }
  | { status: 'unavailable' }

function App() {
  const [connection, setConnection] = useState<ConnectionState>({
    status: 'checking',
  })

  useEffect(() => {
    let isActive = true

    getHealth()
      .then((health) => {
        if (isActive) {
          setConnection({ status: 'connected', health })
        }
      })
      .catch(() => {
        if (isActive) {
          setConnection({ status: 'unavailable' })
        }
      })

    return () => {
      isActive = false
    }
  }, [])

  const connectionMessage =
    connection.status === 'connected'
      ? `Connected to ${connection.health.service}.`
      : connection.status === 'unavailable'
        ? 'Backend unavailable. Start the FastAPI service and refresh this page.'
        : 'Checking backend connection…'

  return (
    <main>
      <p className="eyebrow">NEPSE market analytics platform</p>
      <h1>MarketMitra</h1>
      <p className="description">Project foundation is ready.</p>
      <p className={`connection connection--${connection.status}`}>
        {connectionMessage}
      </p>
    </main>
  )
}

export default App
