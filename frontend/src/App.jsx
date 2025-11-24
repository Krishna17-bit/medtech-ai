import { useState, useEffect } from "react";
import axios from "axios";
import "./App.css";

function App() {
  const [deviceName, setDeviceName] = useState("");
  const [purpose, setPurpose] = useState("training");
  const [language, setLanguage] = useState("en");
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null);

  // ============= Progress Bar Animation =============
  useEffect(() => {
    let interval = null;

    if (loading) {
      setProgress(5); // start at 5%

      interval = setInterval(() => {
        setProgress((old) => {
          if (old >= 90) return old; // wait for backend
          return old + Math.floor(Math.random() * 10) + 1;
        });
      }, 700);
    } else {
      setProgress(100);
      setTimeout(() => setProgress(0), 800);
    }

    return () => clearInterval(interval);
  }, [loading]);

  // Generate prompt template
  const generatePrompt = () => {
    return `
Write a ${purpose}-focused explainer about the medical device: ${deviceName}.
Include:
- Where and when it was invented
- How it works
- Technical process
- Benefits and safety
Language: ${language.toUpperCase()}
`.trim();
  };

  // Handle generation
  const handleGenerate = async () => {
    if (!deviceName) return alert("Please enter a device name");

    const promptText = prompt || generatePrompt();
    setPrompt(promptText);
    setLoading(true);
    setResult(null);

    try {
      const res = await axios.post("http://127.0.0.1:8000/generate", {
        device_name: deviceName,
        purpose,
        language
      });

      setResult(res.data);
    } catch (err) {
      console.error(err);
      alert("Error generating content. Check backend logs.");
    } finally {
      setLoading(false);
    }
  };

  // Download generated video
  const downloadVideo = () => {
    if (!result?.video_url) return;

    const link = document.createElement("a");
    link.href = result.video_url;
    link.download = `${deviceName.replace(/\s+/g, "_")}_video.mp4`;
    link.click();
  };

  return (
    <div className="app-container">
      {/* Sidebar */}
      <aside className="sidebar">
        <h2>MedTech AI</h2>
        <nav>
          <a className="active" href="#">
            Generator
          </a>
          <a href="#">Reports</a>
          <a href="#">History</a>
          <a href="#">Compliance</a>
          <a href="#">Settings</a>
        </nav>
      </aside>

      {/* Main */}
      <main className="main-content">
        <header className="dashboard-header">
          <h1>
            <span>Agentic</span> AI Dashboard
          </h1>
          <div className="badge">Powered by Gemini & Runway</div>
        </header>

        <div id="root-card">
          <h2 className="section-title">AI Content Generator</h2>

          {/* Inputs */}
          <div className="controls">
            <input
              type="text"
              placeholder="Enter device name"
              value={deviceName}
              onChange={(e) => setDeviceName(e.target.value)}
            />

            <select
              value={purpose}
              onChange={(e) => setPurpose(e.target.value)}
            >
              <option value="training">Training</option>
              <option value="marketing">Marketing</option>
              <option value="education">Education</option>
            </select>

            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
            >
              <option value="en">English</option>
              <option value="es">Spanish</option>
              <option value="fr">French</option>
              <option value="de">German</option>
              <option value="hi">Hindi</option>
            </select>
          </div>

          {/* Prompt */}
          <div className="prompt-editor">
            <textarea
              placeholder="View or edit the AI prompt here..."
              value={prompt || generatePrompt()}
              onChange={(e) => setPrompt(e.target.value)}
            />
          </div>

          {/* Progress Bar */}
          {loading && (
            <div className="progress-container">
              <div
                className="progress-bar"
                style={{ width: `${progress}%` }}
              ></div>
            </div>
          )}

          <button onClick={handleGenerate} disabled={loading}>
            {loading ? "Generating..." : "Generate"}
          </button>

          {/* Results */}
          {result && (
            <div className="results">
              <div className="section">
                <h2>Script</h2>
                <p>{result.script}</p>
              </div>

              <div className="section">
                <h2>Research Summary</h2>
                <p>{result.research_used}</p>
              </div>

              <div className="section">
                <h2>Compliance Check</h2>
                <p
                  className={
                    result.compliance_passed
                      ? "compliance-pass"
                      : "compliance-fail"
                  }
                >
                  {result.compliance_passed
                    ? "Compliant"
                    : "Non-Compliant"}
                </p>
              </div>

              <div className="section video">
                <h2>Generated Video</h2>

                {result.video_url ? (
                  <>
                    <video src={result.video_url} controls />

                    <br />
                    <button
                      style={{
                        marginTop: "15px",
                        background: "#4caf50",
                        color: "white"
                      }}
                      onClick={downloadVideo}
                    >
                      Download Video
                    </button>
                  </>
                ) : (
                  <p>No video generated</p>
                )}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;
