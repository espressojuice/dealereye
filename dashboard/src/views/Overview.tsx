import React, { useState, useEffect } from 'react';

// Metric tiles for overview dashboard
const MetricTile = ({ title, value, unit, status, subtitle }: any) => {
  const statusColors = {
    good: 'bg-green-100 text-green-800',
    warning: 'bg-yellow-100 text-yellow-800',
    critical: 'bg-red-100 text-red-800',
  };

  return (
    <div className="bg-white overflow-hidden shadow rounded-lg">
      <div className="p-5">
        <div className="flex items-center justify-between">
          <div className="flex-1">
            <p className="text-sm font-medium text-gray-500 truncate">{title}</p>
            <div className="mt-1 flex items-baseline">
              <p className="text-3xl font-semibold text-gray-900">{value}</p>
              <p className="ml-2 text-sm text-gray-500">{unit}</p>
            </div>
            {subtitle && <p className="mt-1 text-xs text-gray-500">{subtitle}</p>}
          </div>
          {status && (
            <div className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${statusColors[status]}`}>
              {status.toUpperCase()}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const Overview = () => {
  const [metrics, setMetrics] = useState({
    ttg: { value: 0, status: 'good' },
    lobbyCount: 0,
    throughput: 0,
    activeAlerts: 0,
  });

  useEffect(() => {
    // Fetch current metrics from API
    // This would connect to your FastAPI backend
    const fetchMetrics = async () => {
      try {
        // TODO: Replace with actual API call
        // const response = await fetch('http://localhost:8000/api/v1/metrics/current');
        // const data = await response.json();

        // Simulated data
        setMetrics({
          ttg: { value: 85, status: 'good' },
          lobbyCount: 12,
          throughput: 47,
          activeAlerts: 2,
        });
      } catch (error) {
        console.error('Failed to fetch metrics:', error);
      }
    };

    fetchMetrics();
    const interval = setInterval(fetchMetrics, 5000); // Refresh every 5 seconds

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Service Drive Overview</h2>
        <p className="mt-1 text-sm text-gray-500">
          Real-time metrics for Texarkana Toyota
        </p>
      </div>

      {/* Metric Tiles */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        <MetricTile
          title="Time to Greet"
          value={metrics.ttg.value}
          unit="seconds"
          status={metrics.ttg.status}
          subtitle="SLA: < 120s"
        />
        <MetricTile
          title="Lobby Now"
          value={metrics.lobbyCount}
          unit="persons"
          subtitle="Real-time count"
        />
        <MetricTile
          title="Today's Throughput"
          value={metrics.throughput}
          unit="vehicles"
          subtitle="Service lane arrivals"
        />
        <MetricTile
          title="Active Alerts"
          value={metrics.activeAlerts}
          unit="alerts"
          status={metrics.activeAlerts > 0 ? 'warning' : 'good'}
        />
      </div>

      {/* Recent Activity */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Recent Activity</h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500">10:45 AM</span>
              <span className="text-gray-900">Vehicle arrived at service lane 1</span>
              <span className="text-green-600">Greeted in 72s</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500">10:42 AM</span>
              <span className="text-gray-900">Bay 3 service completed</span>
              <span className="text-blue-600">45m rack time</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500">10:38 AM</span>
              <span className="text-gray-900">Customer entered lobby</span>
              <span className="text-gray-400">Lobby: 13 persons</span>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Quick Actions</h3>
          <div className="grid grid-cols-2 gap-4">
            <button className="inline-flex items-center justify-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50">
              View All Alerts
            </button>
            <button className="inline-flex items-center justify-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50">
              Generate Report
            </button>
            <button className="inline-flex items-center justify-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50">
              Camera Health
            </button>
            <button className="inline-flex items-center justify-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50">
              Settings
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Overview;
