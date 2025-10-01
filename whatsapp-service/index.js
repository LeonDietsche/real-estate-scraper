import express from 'express';
import qrcode from 'qrcode-terminal';
import Boom from '@hapi/boom';
import {
  default as makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion
} from '@whiskeysockets/baileys';

const app = express();
app.use(express.json());

let sock;
let reconnectTimer = null;

async function logGroupJIDs() {
  if (!sock) {
    console.log('❌ No WhatsApp connection.');
    return;
  }
  const groups = await sock.groupFetchAllParticipating();
  console.log(`📢 Participating in ${Object.keys(groups).length} groups:`);
  for (const [jid, group] of Object.entries(groups)) {
    console.log(`- ${group.subject || '(no subject)'} → ${jid}`);
  }
}

app.get('/health', (_req, res) => {
  res.json({ ok: Boolean(sock), connected: Boolean(sock?.user) });
});

app.post('/send-message', async (req, res) => {
  let { jid, message } = req.body;
  if (!sock) return res.status(500).send("Socket not ready");

  // --- normalize JID ---
  // If user phone number comes as "4179xxxxxxx" or "+4179xxxxxxx", convert to "@s.whatsapp.net"
  if (jid && !jid.includes('@')) {
    jid = jid.replace(/^\+/, '');        // drop leading plus
    jid = `${jid}@s.whatsapp.net`;
  }

  // Minimal validation
  const isGroup = jid?.endsWith('@g.us');
  const isUser  = jid?.endsWith('@s.whatsapp.net');
  if (!isGroup && !isUser) {
    return res.status(400).json({ success: false, error: 'Invalid JID. Use <phone>@s.whatsapp.net or <id>@g.us' });
  }

  try {
    // Disable link preview to avoid requiring 'link-preview-js'
    await sock.sendMessage(jid, { text: message });
    console.log(`📨 Sent to ${jid}: ${message}`);
    res.send({ success: true });
  } catch (err) {
    console.error('❌ Error sending message:', err);
    res.status(500).send({ success: false, error: err.message });
  }
});

app.get('/groups', async (_req, res) => {
  if (!sock) return res.status(500).json({ error: 'socket not ready' });
  try {
    const groups = await sock.groupFetchAllParticipating();
    const list = Object.entries(groups).map(([jid, g]) => ({
      jid,
      subject: g.subject,
      // show what we detect as parent/community for each group
      parentCandidates: {
        parentJid: g.parentJid || null,
        communityParentJid: g.communityParentJid || null,
        linkedParentJid: g.linkedParentJid || null,
        nestedCommunityParent: g.community?.parentJid || null,
        nestedParentJid: g.parent?.jid || null,
      },
      // quick flags if Baileys exposes them
      isCommunityAnnounce: Boolean(g.isCommunityAnnounce),
      isCommunity: Boolean(g.isCommunity),
      isCommunityLinked: Boolean(g.isCommunityLinked),
      // helpful raw hints without dumping the whole object
      rawKeys: Object.keys(g).slice(0, 40)
    }));
    res.json({ count: list.length, groups: list });
  } catch (e) {
    res.status(500).json({ error: e?.message || String(e) });
  }
});

async function startSock() {
  try {
    const { state, saveCreds } = await useMultiFileAuthState('./auth');
    const { version } = await fetchLatestBaileysVersion(); // keep in sync with WA Web

    sock = makeWASocket({
      auth: state,
      version,
      browser: ['Chrome', 'Windows', '10'],
      printQRInTerminal: false
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', (update) => {
      const { connection, lastDisconnect, qr } = update;

      if (qr) {
        console.log('📱 Scan this QR code to log in (refreshes ~20s):');
        qrcode.generate(qr, { small: true });
      }

      if (connection === 'open') {
        console.log('✅ Connected to WhatsApp!');
        if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
          logGroupJIDs().catch(() => {});
      }

      if (connection === 'close') {
        const err = lastDisconnect?.error;
        const boom = Boom.isBoom(err) ? err : Boom.boomify(err || new Error('Unknown'));
        const status = boom.output?.statusCode;
        console.error('❌ Connection closed. status=', status, 'message=', boom.message);

        const shouldReconnect = status !== DisconnectReason.loggedOut;
        if (shouldReconnect) {
          if (!reconnectTimer) {
            reconnectTimer = setTimeout(() => {
              reconnectTimer = null;
              startSock().catch(e => console.error('Reconnect failed:', e?.message || e));
            }, 2000);
          }
        } else {
          console.log('🛑 Logged out. Delete ./auth and re-pair to continue.');
        }
      }
    });
  } catch (e) {
    console.error('🔥 startSock error:', e?.message || e);
    setTimeout(() => startSock().catch(() => {}), 3000);
  }
}

startSock().then(() => {
  const port = process.env.PORT || 3000;
  app.listen(port, () => console.log(`🚀 WhatsApp service listening on port ${port}`));
});
