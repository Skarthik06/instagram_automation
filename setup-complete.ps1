# Instagram Dashboard - Complete Automated Setup Script
# Run this in PowerShell from your instagram_automation folder

Write-Host "🚀 Starting Instagram Dashboard Setup..." -ForegroundColor Cyan
Write-Host ""

# Step 1: Delete existing dashboard
if (Test-Path "instagram-dashboard") {
    Write-Host "🗑️  Deleting existing dashboard..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force instagram-dashboard
    Write-Host "✅ Deleted old dashboard" -ForegroundColor Green
}

# Step 2: Create new Vite React project
Write-Host ""
Write-Host "📦 Creating new React project..." -ForegroundColor Cyan
npm create vite@latest instagram-dashboard -- --template react
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to create Vite project" -ForegroundColor Red
    exit 1
}
Write-Host "✅ React project created" -ForegroundColor Green

# Step 3: Navigate to project
Set-Location instagram-dashboard

# Step 4: Install dependencies
Write-Host ""
Write-Host "📦 Installing dependencies..." -ForegroundColor Cyan
npm install
npm install axios
npm install -D tailwindcss postcss autoprefixer
Write-Host "✅ Dependencies installed" -ForegroundColor Green

# Step 5: Initialize Tailwind
Write-Host ""
Write-Host "🎨 Setting up Tailwind CSS..." -ForegroundColor Cyan
npx tailwindcss init -p
Write-Host "✅ Tailwind initialized" -ForegroundColor Green

# Step 6: Delete unnecessary files
Write-Host ""
Write-Host "🧹 Cleaning up default files..." -ForegroundColor Cyan
if (Test-Path "src/App.css") { Remove-Item src/App.css -Force }
if (Test-Path "src/assets") { Remove-Item -Recurse src/assets -Force }
Write-Host "✅ Cleanup complete" -ForegroundColor Green

# Step 7: Create App.jsx
Write-Host ""
Write-Host "📝 Creating App.jsx..." -ForegroundColor Cyan
$appContent = @'
import { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE_URL = 'http://127.0.0.1:8000';

function App() {
  const [stats, setStats] = useState({ total_posts: 0, has_pending_previews: false });
  const [analytics, setAnalytics] = useState({ overview: {}, recent_activity: [] });
  const [previews, setPreviews] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);
  const [showAllPosts, setShowAllPosts] = useState(false);
  const [allPosts, setAllPosts] = useState([]);
  const [loadingPosts, setLoadingPosts] = useState(false);

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/stats`);
      setStats(response.data);
    } catch (error) {
      console.error('Error fetching stats:', error);
    }
  };

  const fetchAnalytics = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/analytics`);
      setAnalytics(response.data);
    } catch (error) {
      console.error('Error fetching analytics:', error);
    }
  };

  const fetchCurrentPreviews = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/current-previews`);
      setPreviews(response.data);
    } catch (error) {
      console.error('Error fetching previews:', error);
    }
  };

  const generatePreviews = async () => {
    setLoading(true);
    try {
      const response = await axios.post(`${API_BASE_URL}/api/generate-previews`);
      setPreviews(response.data);
      showMessage('Previews generated successfully!', 'success');
    } catch (error) {
      showMessage('Error generating previews', 'error');
      console.error('Error generating previews:', error);
    } finally {
      setLoading(false);
    }
  };

  const postImage = async (imageIndex) => {
    if (!window.confirm(`Post preview ${imageIndex + 1} to Instagram?`)) return;
    
    setLoading(true);
    try {
      await axios.post(`${API_BASE_URL}/api/post-image`, { image_index: imageIndex });
      showMessage('Posted to Instagram successfully!', 'success');
      setPreviews(null);
      await fetchStats();
    } catch (error) {
      showMessage('Error posting to Instagram', 'error');
      console.error('Error posting image:', error);
    } finally {
      setLoading(false);
    }
  };

  const rejectPreviews = async () => {
    if (!window.confirm('Reject all current previews?')) return;
    
    setLoading(true);
    try {
      await axios.post(`${API_BASE_URL}/api/reject-previews`);
      setPreviews(null);
      showMessage('Previews rejected', 'info');
    } catch (error) {
      showMessage('Error rejecting previews', 'error');
      console.error('Error rejecting previews:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchAllPosts = async () => {
    setLoadingPosts(true);
    try {
      const response = await axios.get(`${API_BASE_URL}/api/posts`, {
        params: { limit: 100, offset: 0 }
      });
      setAllPosts(response.data);
      setShowAllPosts(true);
    } catch (error) {
      showMessage('Error loading posts', 'error');
      console.error('Error fetching posts:', error);
    } finally {
      setLoadingPosts(false);
    }
  };

  const showMessage = (text, type = 'info') => {
    setMessage({ text, type });
    setTimeout(() => setMessage(null), 3000);
  };

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return 'Unknown';
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;
    const hours = Math.floor(diff / 1000 / 60 / 60);
    const days = Math.floor(hours / 24);
    
    if (days > 0) return `${days}d ago`;
    if (hours > 0) return `${hours}h ago`;
    return 'Just now';
  };

  useEffect(() => {
    fetchStats();
    fetchAnalytics();
    fetchCurrentPreviews();

    const interval = setInterval(() => {
      fetchStats();
      fetchAnalytics();
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  const recentPosts = analytics.recent_activity?.slice(0, 5) || [];

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-900 to-black text-white">
      <header className="sticky top-0 z-40 backdrop-blur-xl bg-gray-900/80 border-b border-gray-700/50">
        <div className="container mx-auto px-4 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-full bg-gradient-to-br from-purple-500 via-pink-500 to-orange-500 flex items-center justify-center text-2xl">
                📷
              </div>
              <div>
                <h1 className="text-2xl font-bold bg-gradient-to-r from-purple-400 via-pink-400 to-orange-400 bg-clip-text text-transparent">
                  Instagram Automation Dashboard
                </h1>
                <p className="text-sm text-gray-400">Production-ready automation platform</p>
              </div>
            </div>
            <div className="flex items-center gap-2 px-4 py-2 bg-green-500/20 border border-green-500/50 rounded-full">
              <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
              <span className="text-sm font-medium text-green-400">Live</span>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8 space-y-8">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          <div className="bg-gray-800/50 backdrop-blur-xl border border-gray-700/50 rounded-xl p-6 hover:scale-105 transition-transform">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-400 text-sm">Total Posts</p>
                <p className="text-3xl font-bold bg-gradient-to-r from-purple-400 to-purple-600 bg-clip-text text-transparent">
                  {stats.total_posts}
                </p>
              </div>
              <span className="text-4xl">📊</span>
            </div>
          </div>

          <div className="bg-gray-800/50 backdrop-blur-xl border border-gray-700/50 rounded-xl p-6 hover:scale-105 transition-transform">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-400 text-sm">Pending Previews</p>
                <p className="text-3xl font-bold bg-gradient-to-r from-orange-400 to-orange-600 bg-clip-text text-transparent">
                  {stats.has_pending_previews ? '3' : '0'}
                </p>
              </div>
              <span className="text-4xl">🖼️</span>
            </div>
          </div>

          <div className="bg-gray-800/50 backdrop-blur-xl border border-gray-700/50 rounded-xl p-6 hover:scale-105 transition-transform">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-400 text-sm">Success Rate</p>
                <p className="text-3xl font-bold bg-gradient-to-r from-pink-400 to-pink-600 bg-clip-text text-transparent">
                  {analytics.overview?.success_rate || 0}%
                </p>
              </div>
              <span className="text-4xl">✅</span>
            </div>
          </div>

          <div className="bg-gray-800/50 backdrop-blur-xl border border-gray-700/50 rounded-xl p-6 hover:scale-105 transition-transform">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-400 text-sm">Posts Today</p>
                <p className="text-3xl font-bold bg-gradient-to-r from-yellow-400 to-yellow-600 bg-clip-text text-transparent">
                  {analytics.overview?.posts_today || 0}
                </p>
              </div>
              <span className="text-4xl">📅</span>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap gap-4 justify-center">
          <button
            onClick={generatePreviews}
            disabled={loading}
            className="px-8 py-3 bg-gradient-to-r from-purple-500 via-pink-500 to-orange-500 hover:from-purple-600 hover:via-pink-600 hover:to-orange-600 rounded-lg font-medium transition-all hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {loading ? (
              <>
                <span className="animate-spin">🔄</span>
                <span>Generating...</span>
              </>
            ) : (
              <>
                <span>➕</span>
                <span>Generate New Previews</span>
              </>
            )}
          </button>

          <button
            onClick={fetchAllPosts}
            disabled={loadingPosts}
            className="px-8 py-3 bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 rounded-lg font-medium transition-all hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            <span>🗄️</span>
            <span>View All Posts</span>
          </button>

          <button
            onClick={() => {
              fetchStats();
              fetchAnalytics();
              fetchCurrentPreviews();
            }}
            className="px-8 py-3 bg-gradient-to-r from-gray-600 to-gray-700 hover:from-gray-700 hover:to-gray-800 rounded-lg font-medium transition-all hover:scale-105 flex items-center gap-2"
          >
            <span>🔄</span>
            <span>Refresh</span>
          </button>
        </div>

        {message && (
          <div className={`p-4 rounded-lg border ${
            message.type === 'success' ? 'bg-green-500/20 border-green-500/50 text-green-400' :
            message.type === 'error' ? 'bg-red-500/20 border-red-500/50 text-red-400' :
            'bg-blue-500/20 border-blue-500/50 text-blue-400'
          }`}>
            {message.text}
          </div>
        )}

        {previews && (
          <div className="space-y-6">
            <div className="bg-gray-800/50 backdrop-blur-xl border border-gray-700/50 rounded-xl p-6 border-l-4 border-l-purple-500">
              <div className="flex items-start gap-3">
                <span className="text-2xl">💬</span>
                <div>
                  <p className="text-sm text-gray-400 mb-2">Quote:</p>
                  <p className="text-xl font-medium">{previews.quote}</p>
                </div>
              </div>
            </div>

            <div className="bg-gray-800/50 backdrop-blur-xl border border-gray-700/50 rounded-xl p-6">
              <p className="text-sm text-gray-400 mb-2">Caption:</p>
              <p>{previews.caption}</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {previews.previews?.map((preview) => (
                <div key={preview.index} className="bg-gray-800/50 backdrop-blur-xl border border-gray-700/50 rounded-xl p-4 space-y-4">
                  <div className="relative">
                    <img
                      src={preview.url}
                      alt={`Preview ${preview.index + 1}`}
                      className="w-full aspect-square object-cover rounded-lg"
                    />
                    <div className="absolute top-2 right-2 bg-purple-500 text-white px-3 py-1 rounded-full text-sm font-medium">
                      {preview.index + 1}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="px-3 py-1 bg-green-500/20 border border-green-500/50 rounded-full text-sm text-green-400">
                      Ready
                    </span>
                  </div>
                  <button
                    onClick={() => postImage(preview.index)}
                    disabled={loading}
                    className="w-full px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 rounded-lg font-medium transition-all hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                  >
                    <span>⬆️</span>
                    <span>Post to Instagram</span>
                  </button>
                </div>
              ))}
            </div>

            <div className="flex justify-center">
              <button
                onClick={rejectPreviews}
                disabled={loading}
                className="px-8 py-3 bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 rounded-lg font-medium transition-all hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                <span>🗑️</span>
                <span>Reject All Previews</span>
              </button>
            </div>
          </div>
        )}

        <div className="space-y-6">
          <h2 className="text-2xl font-bold flex items-center gap-3">
            <span>📄</span>
            <span>Recent Posts</span>
          </h2>
          
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-6">
            {recentPosts.map((post, index) => (
              <div key={index} className="bg-gray-800/50 backdrop-blur-xl border border-gray-700/50 rounded-xl overflow-hidden hover:scale-105 transition-transform">
                {post.image_url ? (
                  <img src={post.image_url} alt="Post" className="w-full h-32 object-cover" />
                ) : (
                  <div className="w-full h-32 bg-gradient-to-br from-purple-500 to-pink-500"></div>
                )}
                <div className="p-4 space-y-2">
                  <p className="text-sm line-clamp-3">{post.quote || 'No quote'}</p>
                  <div className="flex items-center gap-2 text-xs text-gray-400">
                    <span>🕐</span>
                    <span>{formatTimestamp(post.timestamp)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </main>

      {showAllPosts && (
        <div 
          className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setShowAllPosts(false)}
        >
          <div 
            className="bg-gray-800 rounded-xl max-w-4xl w-full max-h-[80vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-6 border-b border-gray-700">
              <h2 className="text-2xl font-bold flex items-center gap-3">
                <span>🗄️</span>
                <span>All Posts ({allPosts.length})</span>
              </h2>
              <button
                onClick={() => setShowAllPosts(false)}
                className="text-gray-400 hover:text-white text-2xl"
              >
                ❌
              </button>
            </div>
            
            <div className="overflow-y-auto p-6">
              <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
                {allPosts.map((post) => (
                  <div key={post.id} className="bg-gray-700/50 rounded-xl overflow-hidden hover:bg-gradient-to-br hover:from-purple-500/20 hover:to-pink-500/20 transition-all">
                    {post.image_url ? (
                      <img src={post.image_url} alt="Post" className="w-32 h-32 object-cover mx-auto" />
                    ) : (
                      <div className="w-32 h-32 bg-gradient-to-br from-purple-500 to-pink-500 mx-auto"></div>
                    )}
                    <div className="p-4 space-y-2">
                      <p className="text-sm">{post.quote}</p>
                      <div className="flex items-center gap-2 text-xs text-gray-400">
                        <span className="px-2 py-1 bg-purple-500/20 rounded-full">#{post.id}</span>
                        <span>🕐 {formatTimestamp(post.timestamp)}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
'@
$appContent | Out-File -FilePath "src/App.jsx" -Encoding utf8
Write-Host "✅ App.jsx created" -ForegroundColor Green

# Step 8: Create index.css
Write-Host ""
Write-Host "📝 Creating index.css..." -ForegroundColor Cyan
$cssContent = @'
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen',
    'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue',
    sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

* {
  box-sizing: border-box;
}
'@
$cssContent | Out-File -FilePath "src/index.css" -Encoding utf8
Write-Host "✅ index.css created" -ForegroundColor Green

# Step 9: Update tailwind.config.js
Write-Host ""
Write-Host "📝 Updating tailwind.config.js..." -ForegroundColor Cyan
$tailwindConfig = @'
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
'@
$tailwindConfig | Out-File -FilePath "tailwind.config.js" -Encoding utf8
Write-Host "✅ tailwind.config.js updated" -ForegroundColor Green

# Step 10: Done!
Write-Host ""
Write-Host "✅ Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Next steps:" -ForegroundColor Cyan
Write-Host "1. Start the dashboard: npm run dev" -ForegroundColor White
Write-Host "2. Open browser: http://localhost:5173/" -ForegroundColor White
Write-Host "3. Start your FastAPI backend on port 8000" -ForegroundColor White
Write-Host ""
Write-Host "🎉 Your Instagram Dashboard is ready!" -ForegroundColor Green
