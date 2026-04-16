async function loadCommunity() {
    const res = await apiFetch('/community/posts');
    if (!res || !res.ok) return;
    const posts = await res.json();
    
    document.getElementById('community-feed').innerHTML = posts.map(p => renderComment(p)).join('');
}

function timeAgo(dateString) {
    if (!dateString) return "Just now";
    const date = new Date(dateString + "Z");
    const seconds = Math.floor((new Date() - date) / 1000);
    let interval = seconds / 31536000;
    if (interval > 1) return Math.floor(interval) + " years ago";
    interval = seconds / 2592000;
    if (interval > 1) return Math.floor(interval) + " months ago";
    interval = seconds / 86400;
    if (interval > 1) return Math.floor(interval) + " days ago";
    interval = seconds / 3600;
    if (interval > 1) return Math.floor(interval) + " hours ago";
    interval = seconds / 60;
    if (interval > 1) return Math.floor(interval) + " m ago";
    return "Just now";
}

function renderComment(node, depth = 0) {
    const indent = Math.min(depth * 20, 120);
    const autoCollapse = depth > 2;

    return `
    <div class="comment-node" style="margin-left:${indent}px" data-depth="${depth}">
      <div class="comment-thread-line"></div>
      <div class="glass-card comment-card" style="margin-bottom:12px">
        <div class="comment-header" style="display:flex;gap:8px;align-items:center;font-size:0.9rem">
          <span style="font-weight:600">${node.author_name}</span>
          <span class="badge" style="background:#F1F5F9;color:#64748B">${node.author_city}</span>
          <span class="badge badge-${node.author_platform.toLowerCase()}">${node.author_platform}</span>
          <span style="color:#94A3B8">${timeAgo(node.created_at)}</span>
        </div>
        <p style="margin:12px 0">${node.content}</p>
        <div class="comment-actions" style="display:flex;gap:12px">
          <button class="btn-ghost" style="padding:6px 12px" onclick="toggleLike('${node.id}')">\ud83d\udc4d ${node.likes}</button>
          <button class="btn-ghost" style="padding:6px 12px" onclick="showReplyBox('${node.id}')">\ud83d\udcac Reply</button>
        </div>
        <div id="reply-box-${node.id}" style="display:none;margin-top:12px">
          <textarea id="reply-text-${node.id}" style="width:100%;padding:8px" placeholder="Write a reply..."></textarea>
          <button class="btn-primary" style="padding:6px 12px;margin-top:8px" onclick="submitReply('${node.id}')">Post</button>
        </div>
      </div>
      <div id="children-${node.id}">
        ${(node.replies || []).map(child => renderComment(child, depth + 1)).join('')}
      </div>
    </div>`;
}

function showReplyBox(id) {
    const b = document.getElementById(`reply-box-${id}`);
    b.style.display = b.style.display === 'none' ? 'block' : 'none';
}

/**
 * WORKER NETWORK & COMMUNITY FEED
 * This module manages the real-time social layer of GigShield.
 * 
 * Logic:
 * 1. Retrieves a list of 'Insights' (posts) from the mock api.js.
 * 2. Renders glassmorphic post cards with dynamic 'Time Ago' stamps.
 * 3. Handles new post broadcasts by updating the local MOCK_STATE.
 */

// loadFeed removed as we use loadCommunity now

/**
 * Handle new data broadcast from a worker.
 */
async function createPost() {
    const text = document.getElementById('new-post-text').value;
    if (!text) return;
    
    showLoading();
    const res = await apiFetch('/community/posts', {
        method: "POST",
        body: JSON.stringify({ text })
    });
    
    if (res && res.ok) {
        document.getElementById('new-post-text').value = '';
        showToast("Insight shared with the network!");
        loadCommunity();
    }
}

async function submitReply(parentId) {
    const txt = document.getElementById(`reply-text-${parentId}`).value;
    if(!txt) return;
    
    await apiFetch('/community/posts', {
        method: "POST", body: JSON.stringify({parent_id: parentId, content: txt})
    });
    showToast("Reply posted!");
    loadCommunity();
}

async function toggleLike(id) {
    await apiFetch(`/community/posts/${id}/like`, { method: "PUT" });
    loadCommunity();
}

if(window.location.pathname.includes('community.html')) {
    window.addEventListener('DOMContentLoaded', loadCommunity);
}
