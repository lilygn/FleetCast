import { useState, useEffect } from 'react';
import axios from 'axios';
import './StationViewer.css';

function StationViewer() {
  const [stationId, setStationId] = useState("GS-1");
  const [data, setData] = useState([]);

  useEffect(() => {
    const fetchData = () =>{
      axios.get(`/api/station/${stationId}`)
      .then(res => setData(res.data.satellites))
      .catch(err => console.error("Failed to fetch:", err))
    };
    fetchData();
    const interval = setInterval(fetchData, 5000); // Refresh every 5 seconds
    return () => clearInterval(interval); // Cleanup on unmount
  }, [stationId]);

  return (
    <div className="station-viewer">
    <h2> Station Telemetry Viewer </h2>
  
    <label htmlFor="station-select">Select Ground Station:</label>
    <select
      id="station-select"
      value={stationId}
      onChange={e => setStationId(e.target.value)}
    >
      {["GS-1", "GS-2", "GS-3", "GS-4", "GS-5", "GS-6", "GS-7"].map(gs => (
        <option key={gs} value={gs}>{gs}</option>
      ))}
    </select>
  
    <ul>
      {data.length === 0 ? (
        <li>No satellites currently connected to {stationId}</li>
      ) : (
        data.map((sat, index) => (
          <li key={index}>
            <strong>{sat.satellite_id}</strong>: {sat.status}, Battery: {sat.battery_level}%, Temp: {sat.temperature}°C
          </li>
        ))
      )}
    </ul>
    <button className="space-button" onClick={() => window.location.href = '/'}>
   Back to Dashboard
</button>

  </div>
  
  );
}

export default StationViewer;
