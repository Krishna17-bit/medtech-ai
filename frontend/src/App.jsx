import { useState } from "react";
import axios from "axios";
import "./App.css";

function App() {
  const [deviceName, setDeviceName] = useState("");
  const [purpose, setPurpose] = useState("training");
  const [language, setLanguage] = useState("en");
  const [geminiKey, setGeminiKey] = useState("");
  const [runwayKey, setRunwayKey] = useState("");
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

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
    if (!geminiKey)
      return alert("Please enter Gemini API key");
    if (!runwayKey)
      return alert("Please enter Runway API key");

    const promptText = prompt || generatePrompt();
    setPrompt(promptText);
    setLoading(true);
    setResult(null);

    try {
      const res = await axios.post("http://127.0.0.1:8000/generate", {
        device_name: deviceName,
        purpose,
        language,
        gemini_api_key: geminiKey,
        runway_api_key: runwayKey,
      });

      setResult(res.data);
    } catch (err) {
      console.error(err);
      alert("Error generating content. Check backend console or API keys.");
    } finally {
      setLoading(false);
    }
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

      {/* Main Content */}
      <main className="main-content">
        <header className="dashboard-header">
          <h1>
            <span>Agentic</span> AI Dashboard
          </h1>
          <div className="badge">Powered by Gemini & Runway</div>
        </header>

        {/* Generator Card */}
        <div id="root-card">
          <h2 className="section-title">AI Content Generator</h2>

          {/* API Keys */}
          <div className="controls">
            <input
              type="password"
              placeholder="Enter Gemini API Key"
              value={geminiKey}
              onChange={(e) => setGeminiKey(e.target.value)}
            />
            <input
              type="password"
              placeholder="Enter Runway API Key"
              value={runwayKey}
              onChange={(e) => setRunwayKey(e.target.value)}
            />
          </div>

          {/* Device and Settings */}
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

          {/* Prompt Box */}
          <div className="prompt-editor">
            <textarea
              placeholder="View or edit the AI prompt here..."
              value={prompt || generatePrompt()}
              onChange={(e) => setPrompt(e.target.value)}
            />
          </div>

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
                  <video src={result.video_url} width="100%" controls />
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
