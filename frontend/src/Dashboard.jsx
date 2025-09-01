import { useEffect, useState } from 'react';
import axios from 'axios';
import './Dashboard.css';

function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [utcTime, setUtcTime] = useState(new Date().toUTCString());

  // Fetch summary using Axios
  useEffect(() => {
    const fetchData = () => {
        axios.get(`'http://localhost:3000/api/dashboard`)
  .then(res => {
    console.log("Dashboard data:", res.data);  // <-- Add this
    setSummary(res.data);
  })
  .catch(err => {
    console.error("Failed to fetch dashboard data:", err);
  }); 
}
    fetchData();
    const interval = setInterval(fetchData, 5000); // Refresh every 5 seconds
    return () => clearInterval(interval); // Cleanup on unmount
  }, []);

  // Update UTC time every second
  useEffect(() => {
    const interval = setInterval(() => {
      setUtcTime(new Date().toUTCString());
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  if (!summary) return <p>Loading dashboard...</p>;

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h2> Mission Control Dashboard</h2>
        <p> {utcTime} 🕒</p>
      </div>
      <div className="summary-cards">
        <div className="card sat"><h3>{summary.totalSatellites}</h3><p>Total Satellites</p></div>
        <div className="card contact"><h3>{summary.activeContacts}</h3><p>Satellites in Contact</p></div>
        <div className="card low"><h3>{summary.lowBattery}</h3><p>Low Battery</p></div>
        <div className="card error"><h3>{summary.errorState}</h3><p>Error State</p></div>
      </div>
      <div className="blackhole-container">
  <button
    className="blackhole-button"
    onClick={() => window.open('/station-viewer', '_blank')}
  >
    Launch Station Viewer
    <div className="star orbit1"></div>
    <div className="star orbit2"></div>
    <div className="star orbit3"></div>
  </button>
</div>



    </div>
    
  );
}

export default Dashboard;
