const express = require('express');
const cors = require('cors');
const dotenv = require('dotenv');

dotenv.config();

const app = express();
app.use(express.json());
app.use(cors({
    origin: [
        process.env.FRONTEND_URL,
        process.env.FIREBASE_LOGIN_URL
    ],
    credentials: true
}));

// Simpan session di memory (simulasi session storage)
const sessionStore = new Map();

app.post('/api/check-keyword', (req, res) => {
    const { keyword } = req.body;
    if (keyword === process.env.SECRET_KEYWORD) {
        const sessionId = Date.now().toString();
        sessionStore.set(sessionId, { keywordValid: true });
        return res.json({ success: true, sessionId });
    }
    return res.status(401).json({ error: 'Invalid keyword' });
});

app.get('/api/auth/github', (req, res) => {
    const { sessionId } = req.query;
    if (!sessionStore.has(sessionId)) {
        return res.status(401).json({ error: 'Unauthorized' });
    }
    const params = new URLSearchParams({
        client_id: process.env.GITHUB_CLIENT_ID,
        redirect_uri: `${process.env.GITHUB_REDIRECT_URI}?sessionId=${sessionId}`,
        scope: 'user:email'
    }).toString();
    res.redirect(`https://github.com/login/oauth/authorize?${params}`);
});

app.get('/api/auth/github/callback', async (req, res) => {
    const { code, sessionId } = req.query;
    if (!sessionStore.has(sessionId)) {
        return res.redirect(process.env.FIREBASE_LOGIN_URL);
    }

    const tokenRes = await fetch('https://github.com/login/oauth/access_token', {
        method: 'POST',
        headers: { Accept: 'application/json' },
        body: new URLSearchParams({
            client_id: process.env.GITHUB_CLIENT_ID,
            client_secret: process.env.GITHUB_CLIENT_SECRET,
            code
        })
    }).then(res => res.json());

    const userData = await fetch('https://api.github.com/user', {
        headers: { Authorization: `Bearer ${tokenRes.access_token}` }
    }).then(res => res.json());

    sessionStore.set(sessionId, { keywordValid: true, userData });
    res.redirect(`${process.env.FRONTEND_URL}/profile.html?sessionId=${sessionId}`);
});

app.get('/api/profile', (req, res) => {
    const { sessionId } = req.query;
    const session = sessionStore.get(sessionId);
    if (!session) {
        return res.status(401).json({ error: 'Unauthorized' });
    }

    if (session.userData) {
        return res.json({ type: 'github', data: session.userData });
    }
    return res.json({
        type: 'keyword',
        data: {
            name: 'Guest User',
            avatar_url: 'https://via.placeholder.com/150',
            message: 'Logged in with secret keyword'
        }
    });
});

app.get('/api/logout', (req, res) => {
    const { sessionId } = req.query;
    sessionStore.delete(sessionId);
    res.json({ success: true });
});

module.exports = app;
