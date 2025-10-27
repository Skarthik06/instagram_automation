import { useState, useEffect } from 'react';
import api from './services/api';

function App() {
  const [stats, setStats] = useState({ total_posts: 0, has_pending_previews: false });
  const [analytics, setAnalytics] = useState(null);
  const [previews, setPreviews] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);
  const [showAllPosts, setShowAllPosts] = useState(false);
  const [allPosts, setAllPosts] = useState([]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchData = async () => {
    try {
      const [statsData, analyticsData] = await Promise.all([api.getStats(), api.getAnalytics()]);
      setStats(statsData);
      setAnalytics(analyticsData);
    } catch (error) {
      console.error('Error:', error);
    }
  };

  const handleGeneratePreviews = async () => {
    setLoading(true);
    setMessage(null);
    try {
      const data = await api.generatePreviews();
      setPreviews(data);
      await fetchData();
      setMessage({ type: 'success', text: '✨ Previews generated!' });
      setTimeout(() => setMessage(null), 3000);
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to generate previews' });
    } finally {
      setLoading(false);
    }
  };

  const handlePostImage = async (index) => {
    if (!window.confirm(`Post preview ${index + 1}?`)) return;
    setLoading(true);
    try {
      await api.postImage(index);
      setPreviews(null);
      await fetchData();
      setMessage({ type: 'success', text: '🎉 Posted to Instagram!' });
      setTimeout(() => setMessage(null), 3000);
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to post' });
    } finally {
      setLoading(false);
    }
  };

  const handleRejectPreviews = async () => {
    if (!window.confirm('Reject all previews?')) return;
    setLoading(true);
    try {
      await api.rejectPreviews();
      setPreviews(null);
      setMessage({ type: 'info', text: '✅ Previews rejected' });
      setTimeout(() => setMessage(null), 3000);
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to reject' });
    } finally {
      setLoading(false);
    }
  };

  const handleViewAllPosts = async () => {
    setShowAllPosts(true);
    try {
      const data = await api.getPosts(50, 0);
      setAllPosts(data.posts || []);
    } catch (error) {
      console.error('Error:', error);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-black text-white">
      <div className="container mx-auto px-4 py-8 max-w-7xl">
        
        {/* Header */}
        <div className="bg-gray-800/50 backdrop-blur-xl rounded-3xl shadow-2xl border border-gray-700/50 p-8 mb-8">
          <div className="text-center">
            <h1 className="text-5xl font-bold mb-2 bg-gradient-to-r from-instagram-purple via-instagram-pink to-instagram-orange bg-clip-text text-transparent">
              Instagram Automation
            </h1>
            <p className="text-gray-400">Production-ready automation platform • <span className="text-green-400">● Live</span></p>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          {[
            { title: 'Total Posts', value: stats.total_posts, icon: '📊', color: 'purple' },
            { title: 'This Week', value: analytics?.overview.posts_this_week || 0, icon: '📅', color: 'orange' },
            { title: 'This Month', value: analytics?.overview.posts_this_month || 0, icon: '📈', color: 'pink' },
            { title: 'Pending', value: stats.has_pending_previews ? 'Yes' : 'No', icon: '⏱️', color: 'yellow' }
          ].map((stat, i) => (
            <div key={i} className="bg-gray-800/50 backdrop-blur-xl rounded-2xl p-6 border border-gray-700/50 hover:scale-105 transition">
              <p className="text-gray-400 text-sm uppercase mb-2">{stat.title}</p>
              <div className="flex items-center justify-between">
                <h3 className="text-4xl font-bold">{stat.value}</h3>
                <span className="text-4xl">{stat.icon}</span>
              </div>
            </div>
          ))}
        </div>

        {/* Action Buttons */}
        <div className="bg-gray-800/50 backdrop-blur-xl rounded-2xl p-6 mb-8 border border-gray-700/50">
          <div className="flex flex-wrap gap-4">
            <button onClick={handleGeneratePreviews} disabled={loading}
              className="flex-1 min-w-[200px] gradient-instagram text-white px-8 py-4 rounded-xl font-semibold hover:scale-105 transition disabled:opacity-50">
              {loading ? 'Generating...' : '🎨 Generate Previews'}
            </button>
            <button onClick={handleViewAllPosts}
              className="px-8 py-4 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-semibold hover:scale-105 transition">
              📦 View All Posts
            </button>
            <button onClick={fetchData}
              className="px-8 py-4 bg-gray-700 hover:bg-gray-600 text-white rounded-xl font-semibold hover:scale-105 transition">
              🔄 Refresh
            </button>
          </div>
        </div>

        {/* Message */}
        {message && (
          <div className={`rounded-2xl p-6 mb-8 ${
            message.type === 'success' ? 'bg-green-900/30 border border-green-700/50 text-green-400' :
            message.type === 'error' ? 'bg-red-900/30 border border-red-700/50 text-red-400' :
            'bg-blue-900/30 border border-blue-700/50 text-blue-400'
          }`}>
            <p className="font-semibold">{message.text}</p>
          </div>
        )}

        {/* Previews */}
        {previews && previews.previews && (
          <div className="mb-8 space-y-8">
            <div className="bg-gradient-to-r from-purple-900/30 to-pink-900/30 rounded-3xl p-8 border border-purple-700/50">
              <h3 className="text-2xl font-bold mb-4">"{previews.quote}"</h3>
              <p className="text-gray-400">{previews.caption}</p>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              {previews.previews.map((preview) => (
                <div key={preview.index} className="bg-gray-800/50 rounded-3xl overflow-hidden border border-gray-700/50 hover:scale-105 transition">
                  <img src={preview.url} alt={`Preview ${preview.index + 1}`} className="w-full h-96 object-cover" />
                  <div className="p-6">
                    <button onClick={() => handlePostImage(preview.index)} disabled={loading}
                      className="w-full gradient-instagram text-white py-4 rounded-xl font-semibold hover:scale-105 transition disabled:opacity-50">
                      📤 Post to Instagram
                    </button>
                  </div>
                </div>
              ))}
            </div>

            <div className="text-center">
              <button onClick={handleRejectPreviews} disabled={loading}
                className="px-12 py-4 bg-red-600 hover:bg-red-700 text-white rounded-xl font-semibold hover:scale-105 transition disabled:opacity-50">
                🗑️ Reject All Previews
              </button>
            </div>
          </div>
        )}

        {/* Recent Posts */}
        <div className="bg-gray-800/50 backdrop-blur-xl rounded-3xl p-8 border border-gray-700/50">
          <h2 className="text-3xl font-bold mb-6">Recent Posts (Last 5)</h2>
          <div className="space-y-4">
            {analytics?.recent_activity.last_5_posts.length > 0 ? (
              analytics.recent_activity.last_5_posts.map((post, i) => (
                <div key={i} className="flex gap-6 p-6 bg-gray-700/30 rounded-2xl hover:bg-gray-700/50 transition">
                  {post.image_url ? (
                    <img src={post.image_url} alt="Post" className="w-24 h-24 rounded-xl object-cover" />
                  ) : (
                    <div className="w-24 h-24 rounded-xl gradient-instagram flex items-center justify-center text-4xl">📷</div>
                  )}
                  <div className="flex-1">
                    <p className="text-gray-300 mb-2">{post.quote}</p>
                    <p className="text-gray-500 text-sm">🕒 {post.posted_at}</p>
                  </div>
                </div>
              ))
            ) : (
              <p className="text-gray-500 text-center py-16">No posts yet. Create your first post!</p>
            )}
          </div>
        </div>

        {/* All Posts Modal */}
        {showAllPosts && (
          <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={() => setShowAllPosts(false)}>
            <div className="bg-gray-800 rounded-3xl p-8 max-w-6xl w-full max-h-[90vh] overflow-hidden flex flex-col" onClick={(e) => e.stopPropagation()}>
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-3xl font-bold">All Posts ({allPosts.length})</h2>
                <button onClick={() => setShowAllPosts(false)} className="text-gray-400 hover:text-white text-3xl">×</button>
              </div>
              <div className="flex-1 overflow-y-auto space-y-4">
                {allPosts.map((post) => (
                  <div key={post.id} className="flex gap-6 p-6 bg-gray-700/30 rounded-2xl hover:bg-gray-700/50 transition">
                    {post.image_url ? (
                      <img src={post.image_url} alt="Post" className="w-32 h-32 rounded-xl object-cover" />
                    ) : (
                      <div className="w-32 h-32 rounded-xl gradient-instagram flex items-center justify-center text-5xl">📷</div>
                    )}
                    <div className="flex-1">
                      <span className="inline-block bg-gradient-to-r from-instagram-purple to-instagram-pink text-white px-3 py-1 rounded-full text-xs font-bold mb-2">
                        #{post.id}
                      </span>
                      <p className="text-gray-300 mb-2">{post.quote}</p>
                      <p className="text-gray-500 text-sm">🕒 {post.posted_at}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
