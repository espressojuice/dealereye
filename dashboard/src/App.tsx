import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';

// Dashboard views
import Overview from './views/Overview';
import Operations from './views/Operations';
import Historical from './views/Historical';
import CameraSetup from './views/CameraSetup';
import Alerts from './views/Alerts';

function App() {
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    // Connect to WebSocket for live updates
    const ws = new WebSocket(import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/live');

    ws.onopen = () => {
      console.log('WebSocket connected');
      setConnected(true);

      // Subscribe to site metrics
      ws.send(JSON.stringify({
        site_id: 'YOUR_SITE_ID',
        metrics: ['time_to_greet', 'lobby_occupancy', 'drive_throughput']
      }));
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log('Received:', data);
      // Handle live metric updates
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setConnected(false);
    };

    return () => ws.close();
  }, []);

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-100">
        {/* Header */}
        <header className="bg-white shadow">
          <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center">
              <h1 className="text-2xl font-bold text-gray-900">
                DealerEye Analytics
              </h1>
              <div className="flex items-center space-x-4">
                <div className="flex items-center">
                  <div className={`h-2 w-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'} mr-2`}></div>
                  <span className="text-sm text-gray-600">
                    {connected ? 'Connected' : 'Disconnected'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </header>

        {/* Navigation */}
        <nav className="bg-white border-b border-gray-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex space-x-8">
              <Link to="/" className="border-b-2 border-blue-500 py-4 px-1 text-sm font-medium text-blue-600">
                Overview
              </Link>
              <Link to="/operations" className="border-b-2 border-transparent py-4 px-1 text-sm font-medium text-gray-500 hover:text-gray-700 hover:border-gray-300">
                Operations
              </Link>
              <Link to="/historical" className="border-b-2 border-transparent py-4 px-1 text-sm font-medium text-gray-500 hover:text-gray-700 hover:border-gray-300">
                Historical
              </Link>
              <Link to="/alerts" className="border-b-2 border-transparent py-4 px-1 text-sm font-medium text-gray-500 hover:text-gray-700 hover:border-gray-300">
                Alerts
              </Link>
              <Link to="/cameras" className="border-b-2 border-transparent py-4 px-1 text-sm font-medium text-gray-500 hover:text-gray-700 hover:border-gray-300">
                Cameras
              </Link>
            </div>
          </div>
        </nav>

        {/* Main Content */}
        <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/operations" element={<Operations />} />
            <Route path="/historical" element={<Historical />} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/cameras" element={<CameraSetup />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
