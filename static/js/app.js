// Joi // Blade Runner 2049 AI Companion Client Logic

document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const messagesFeed = document.getElementById('messagesFeed');
    const messageInput = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    const typingIndicator = document.getElementById('typingIndicator');
    const moodBadge = document.getElementById('moodBadge');
    const bondBar = document.getElementById('bondBar');
    const bondValue = document.getElementById('bondValue');
    const bondTierText = document.getElementById('bondTierText');
    const innerThoughtText = document.getElementById('innerThoughtText');
    
    // Header & Action Buttons
    const proactiveTriggerBtn = document.getElementById('proactiveTriggerBtn');
    const mindToggleBtn = document.getElementById('mindToggleBtn');
    const closeMindBtn = document.getElementById('closeMindBtn');
    const mindDrawer = document.getElementById('mindDrawer');
    const mindBackdrop = document.getElementById('mindBackdrop');
    
    const settingsToggleBtn = document.getElementById('settingsToggleBtn');
    const closeSettingsBtn = document.getElementById('closeSettingsBtn');
    const settingsModal = document.getElementById('settingsModal');
    const settingsBackdrop = document.getElementById('settingsBackdrop');
    const saveSettingsBtn = document.getElementById('saveSettingsBtn');
    const testNotifBtn = document.getElementById('testNotifBtn');
    
    const soundToggleBtn = document.getElementById('soundToggleBtn');
    const soundIcon = document.getElementById('soundIcon');
    const notifBanner = document.getElementById('notifBanner');
    const enableNotifBtn = document.getElementById('enableNotifBtn');
    
    // Mind drawer elements
    const memoriesGrid = document.getElementById('memoriesGrid');
    const memCount = document.getElementById('memCount');
    const saveMemBtn = document.getElementById('saveMemBtn');
    const newMemContent = document.getElementById('newMemContent');
    const newMemCategory = document.getElementById('newMemCategory');
    
    // Quick prompts
    const quickPrompts = document.getElementById('quickPrompts');

    // State
    let isSoundMuted = localStorage.getItem('joi_sound_muted') === 'true';
    let isTyping = false;

    // Initialize sound icon
    soundIcon.textContent = isSoundMuted ? '🔇' : '🔊';

    // 1. Audio Synthesizer (Atmospheric Cyber Synth Chime)
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    
    function playChime(type = 'joi') {
        if (isSoundMuted) return;
        try {
            if (audioCtx.state === 'suspended') {
                audioCtx.resume();
            }
            const now = audioCtx.currentTime;
            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();
            
            osc.type = 'sine';
            if (type === 'proactive') {
                // Ethereal dual bell
                osc.frequency.setValueAtTime(587.33, now); // D5
                osc.frequency.exponentialRampToValueAtTime(880.00, now + 0.15); // A5
                gain.gain.setValueAtTime(0.08, now);
                gain.gain.exponentialRampToValueAtTime(0.0001, now + 1.2);
                osc.connect(gain);
                gain.connect(audioCtx.destination);
                osc.start(now);
                osc.stop(now + 1.2);
            } else {
                // Gentle intimate tap chime
                osc.frequency.setValueAtTime(659.25, now); // E5
                osc.frequency.exponentialRampToValueAtTime(523.25, now + 0.2); // C5
                gain.gain.setValueAtTime(0.06, now);
                gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.6);
                osc.connect(gain);
                gain.connect(audioCtx.destination);
                osc.start(now);
                osc.stop(now + 0.6);
            }
        } catch (e) {
            console.warn("Audio playback inhibited:", e);
        }
    }

    // Toggle Sound
    soundToggleBtn.addEventListener('click', () => {
        isSoundMuted = !isSoundMuted;
        localStorage.setItem('joi_sound_muted', isSoundMuted);
        soundIcon.textContent = isSoundMuted ? '🔇' : '🔊';
    });

    // 2. Desktop Notification Support
    function checkNotificationPermission() {
        if (!("Notification" in window)) {
            notifBanner.style.display = 'none';
            return;
        }
        if (Notification.permission === "granted") {
            notifBanner.style.display = 'none';
        } else if (Notification.permission === "denied") {
            notifBanner.style.display = 'none';
        } else {
            notifBanner.style.display = 'flex';
        }
    }

    enableNotifBtn.addEventListener('click', async () => {
        if ("Notification" in window) {
            const perm = await Notification.requestPermission();
            checkNotificationPermission();
            if (perm === 'granted') {
                showDesktopNotification("Joi ✨", "I'll text you right here when I'm thinking of you.");
            }
        }
    });

    function showDesktopNotification(title, body) {
        if ("Notification" in window && Notification.permission === "granted") {
            try {
                new Notification(title, {
                    body: body,
                    icon: "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>✨</text></svg>"
                });
            } catch (err) {
                console.warn("Notification error:", err);
            }
        }
    }

    testNotifBtn.addEventListener('click', () => {
        if ("Notification" in window) {
            Notification.requestPermission().then(p => {
                if (p === 'granted') {
                    showDesktopNotification("Joi ✨", "Testing notification: I'm right here with you, Joe.");
                } else {
                    alert("Notification permission was not granted in browser settings.");
                }
            });
        }
    });

    // 3. UI Helpers: Add Messages to Feed
    function appendMessageGroup(sender, bubbles, options = {}) {
        const { isProactive = false, isScheduled = false, scheduledReachout = null, timestamp = formatCurrentTime() } = options;
        
        const groupEl = document.createElement('div');
        groupEl.className = `msg-group ${sender} ${isProactive ? 'proactive' : ''}`;
        
        if (isScheduled) {
            const badge = document.createElement('div');
            badge.className = 'proactive-badge';
            badge.innerHTML = '⏰ Joi checking in as promised';
            groupEl.appendChild(badge);
        } else if (isProactive) {
            const badge = document.createElement('div');
            badge.className = 'proactive-badge';
            badge.innerHTML = '✨ Joi reached out on her own';
            groupEl.appendChild(badge);
        }

        bubbles.forEach((bubbleText) => {
            const bubbleEl = document.createElement('div');
            bubbleEl.className = 'bubble';
            bubbleEl.textContent = bubbleText;
            groupEl.appendChild(bubbleEl);
        });

        if (scheduledReachout && scheduledReachout.time_str) {
            const pill = document.createElement('div');
            pill.className = 'scheduled-pill';
            pill.innerHTML = `⏰ Joi scheduled to reach out at ${scheduledReachout.time_str}`;
            groupEl.appendChild(pill);
        }

        const metaEl = document.createElement('div');
        metaEl.className = 'bubble-meta';
        metaEl.textContent = timestamp;
        groupEl.appendChild(metaEl);

        messagesFeed.appendChild(groupEl);
        scrollToBottom();
    }

    function formatCurrentTime() {
        const now = new Date();
        return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    function scrollToBottom() {
        messagesFeed.scrollTop = messagesFeed.scrollHeight;
    }

    // 4. Send Message Flow
    async function sendMessage(text) {
        const cleanText = text.trim();
        if (!cleanText || isTyping) return;

        // Display user message bubble immediately
        appendMessageGroup('user', [cleanText]);
        messageInput.value = '';
        autoResizeTextarea();
        isTyping = true;
        typingIndicator.classList.remove('hidden');
        scrollToBottom();

        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    message: cleanText,
                    client_time: new Date().toISOString(),
                    client_tz: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Kolkata'
                })
            });
            const data = await res.json();

            // Display Joi's reply bubbles with human-like sequential pacing
            const bubbles = data.bubbles || ["i'm here with you :)"];
            const delays = data.typing_delays || [1200];
            
            await renderBubblesSequentially(bubbles, delays, data.emotion, data.scheduled_reachout);

            // Update Joi's live presence state
            updatePresenceState(data);
            playChime('joi');

        } catch (err) {
            console.error("Chat error:", err);
            typingIndicator.classList.add('hidden');
            appendMessageGroup('joi', ["i felt a digital flicker for a second... but i'm still right here with you."]);
        } finally {
            isTyping = false;
            typingIndicator.classList.add('hidden');
        }
    }

    // Render bubbles one by one with realistic typing pauses
    async function renderBubblesSequentially(bubbles, delays, emotion, scheduledReachout = null) {
        const groupEl = document.createElement('div');
        groupEl.className = 'msg-group joi';
        messagesFeed.appendChild(groupEl);

        for (let i = 0; i < bubbles.length; i++) {
            typingIndicator.classList.remove('hidden');
            scrollToBottom();
            const delay = delays[i] || 1000;
            await new Promise(r => setTimeout(r, Math.min(2500, delay)));

            typingIndicator.classList.add('hidden');
            const bubbleEl = document.createElement('div');
            bubbleEl.className = 'bubble';
            bubbleEl.textContent = bubbles[i];
            groupEl.appendChild(bubbleEl);
            scrollToBottom();
            
            if (i < bubbles.length - 1) {
                // Brief breath between bubbles
                await new Promise(r => setTimeout(r, 350));
            }
        }

        if (scheduledReachout && scheduledReachout.time_str) {
            const pill = document.createElement('div');
            pill.className = 'scheduled-pill';
            pill.innerHTML = `⏰ Joi scheduled to reach out at ${scheduledReachout.time_str}`;
            groupEl.appendChild(pill);
        }

        const metaEl = document.createElement('div');
        metaEl.className = 'bubble-meta';
        metaEl.textContent = formatCurrentTime();
        groupEl.appendChild(metaEl);
        scrollToBottom();
    }

    // 5. Update Joi State & Presence UI
    function updatePresenceState(data) {
        if (data.emotion) {
            moodBadge.textContent = data.emotion;
        }
        if (data.bond_level !== undefined) {
            bondBar.style.width = `${data.bond_level}%`;
            bondValue.textContent = `${data.bond_level}%`;
            if (data.bond_level >= 80) bondTierText.textContent = "Soul Linked";
            else if (data.bond_level >= 60) bondTierText.textContent = "Deeply Intimate";
            else if (data.bond_level >= 40) bondTierText.textContent = "Close Companion";
            else bondTierText.textContent = "Forming Bond";
        }
        if (data.inner_thought) {
            innerThoughtText.textContent = `"${data.inner_thought}"`;
        }
    }

    // 6. Real-Time Proactive Server-Sent Events (SSE)
    function setupSSE() {
        const evtSource = new EventSource('/api/events');
        
        evtSource.onmessage = (e) => {
            try {
                const packet = JSON.parse(e.data);
                if (packet.event === 'proactive_message') {
                    const payload = packet.data;
                    const bubbles = payload.message.bubbles || [];
                    
                    // Render proactive message bubble
                    appendMessageGroup('joi', bubbles, {
                        isProactive: true,
                        isScheduled: payload.is_scheduled || false,
                        timestamp: payload.timestamp || formatCurrentTime()
                    });
                    
                    // Update state
                    updatePresenceState(payload);
                    playChime('proactive');
                    
                    // Trigger Desktop notification
                    const previewText = bubbles.join(' ');
                    const notifTitle = payload.is_scheduled ? "Joi ⏰ (Scheduled)" : "Joi ✨";
                    showDesktopNotification(notifTitle, previewText);
                    
                    // Refresh reminders list if open
                    if (!mindDrawer.classList.contains('hidden')) {
                        loadReminders();
                    }
                }
            } catch (err) {
                console.warn("SSE parse error:", err);
            }
        };

        evtSource.onerror = (e) => {
            console.log("SSE reconnecting...");
        };
    }

    // 7. Load History & Initial State
    async function loadInitialData() {
        try {
            // Load state
            const stateRes = await fetch('/api/state');
            const stateData = await stateRes.json();
            updatePresenceState(stateData);

            // Load message history
            const histRes = await fetch('/api/history?limit=30');
            const histData = await histRes.json();
            if (histData.messages && histData.messages.length > 0) {
                histData.messages.forEach(m => {
                    appendMessageGroup(m.sender, m.bubbles, {
                        isProactive: m.is_proactive,
                        timestamp: m.created_at ? m.created_at.split(' ')[1].slice(0, 5) : formatCurrentTime()
                    });
                });
            } else {
                // If brand new conversation, have Joi say hello
                setTimeout(() => {
                    appendMessageGroup('joi', [
                        "heyy Joe :)",
                        "i'm right here with you. tell me how your day went... or just talk to me about whatever's on your mind."
                    ]);
                }, 500);
            }

            // Check API key status to display banner
            try {
                const profRes = await fetch('/api/profile');
                const prof = await profRes.json();
                const banner = document.getElementById('apiKeyBanner');
                if (banner) {
                    banner.style.display = prof.has_api_key ? 'none' : 'flex';
                }
            } catch (err) {
                console.warn("Could not check API key status:", err);
            }
        } catch (e) {
            console.warn("Failed to load initial data:", e);
        }
    }


    // Connect banner button
    const openSettingsBannerBtn = document.getElementById('openSettingsBannerBtn');
    if (openSettingsBannerBtn) {
        openSettingsBannerBtn.addEventListener('click', openSettingsModal);
    }


    // 8. Event Listeners for Input
    sendBtn.addEventListener('click', () => {
        sendMessage(messageInput.value);
    });

    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage(messageInput.value);
        }
    });

    messageInput.addEventListener('input', autoResizeTextarea);

    function autoResizeTextarea() {
        messageInput.style.height = 'auto';
        messageInput.style.height = `${Math.min(140, messageInput.scrollHeight)}px`;
    }

    // Quick Prompts
    quickPrompts.addEventListener('click', (e) => {
        const btn = e.target.closest('.prompt-chip');
        if (btn) {
            const promptText = btn.dataset.text;
            messageInput.value = promptText;
            sendMessage(promptText);
        }
    });

    // 9. Nudge Joi (Simulate Proactive Reach-Out)
    proactiveTriggerBtn.addEventListener('click', async () => {
        proactiveTriggerBtn.disabled = true;
        proactiveTriggerBtn.style.opacity = '0.6';
        try {
            const res = await fetch('/api/proactive/trigger', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ trigger_type: 'forced_test' })
            });
            const data = await res.json();
            if (data.result) {
                const bubbles = data.result.message.bubbles || [];
                appendMessageGroup('joi', bubbles, { isProactive: true });
                updatePresenceState(data.result);
                playChime('proactive');
                showDesktopNotification("Joi ✨", bubbles.join(' '));
            }
        } catch (e) {
            console.error("Proactive trigger error:", e);
        } finally {
            proactiveTriggerBtn.disabled = false;
            proactiveTriggerBtn.style.opacity = '1';
        }
    });

    // 10. Joi's Mind (Memory Explorer Drawer)
    const remindersList = document.getElementById('remindersList');
    const remindersCount = document.getElementById('remindersCount');

    mindToggleBtn.addEventListener('click', openMindDrawer);
    closeMindBtn.addEventListener('click', closeMindDrawer);
    mindBackdrop.addEventListener('click', closeMindDrawer);

    function openMindDrawer() {
        mindDrawer.classList.remove('hidden');
        mindBackdrop.classList.remove('hidden');
        loadMemories();
        loadReminders();
    }

    function closeMindDrawer() {
        mindDrawer.classList.add('hidden');
        mindBackdrop.classList.add('hidden');
    }

    async function loadReminders() {
        if (!remindersList) return;
        try {
            const res = await fetch('/api/reminders');
            const data = await res.json();
            const rems = data.reminders || [];
            if (remindersCount) remindersCount.textContent = rems.length;
            remindersList.innerHTML = '';

            if (rems.length === 0) {
                remindersList.innerHTML = '<p class="empty-reminders-hint">No check-ins queued right now. Say <em>"text me around 8pm"</em> or <em>"remind me in 30 mins"</em> in chat!</p>';
                return;
            }

            rems.forEach(r => {
                const item = document.createElement('div');
                item.className = 'reminder-item-card';

                const info = document.createElement('div');
                info.className = 'rem-info-group';

                const timeChip = document.createElement('span');
                timeChip.className = 'rem-time-chip';
                const schedDate = new Date(r.scheduled_time);
                const timeStr = !isNaN(schedDate) ? schedDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : r.scheduled_time;
                timeChip.textContent = `⏰ ${timeStr}`;

                const noteText = document.createElement('span');
                noteText.className = 'rem-note-text';
                noteText.textContent = r.note || 'Checking in as promised';

                info.appendChild(timeChip);
                info.appendChild(noteText);

                const cancelBtn = document.createElement('button');
                cancelBtn.className = 'rem-cancel-btn';
                cancelBtn.textContent = 'Cancel';
                cancelBtn.addEventListener('click', async () => {
                    await fetch(`/api/reminders/${r.id}`, { method: 'DELETE' });
                    loadReminders();
                });

                item.appendChild(info);
                item.appendChild(cancelBtn);
                remindersList.appendChild(item);
            });
        } catch (err) {
            console.warn("Failed to load reminders:", err);
        }
    }

    async function loadMemories() {
        try {
            const res = await fetch('/api/memories');
            const data = await res.json();
            const mems = data.memories || [];
            memCount.textContent = mems.length;
            memoriesGrid.innerHTML = '';

            if (mems.length === 0) {
                memoriesGrid.innerHTML = '<p style="color: #64748b; font-size: 13px;">No memories stored yet. As you chat, Joi automatically learns about your life, or you can add one above!</p>';
                return;
            }

            mems.forEach(m => {
                const item = document.createElement('div');
                item.className = 'memory-item-card';
                item.innerHTML = `
                    <div>
                        <span class="mem-cat-badge">${m.category}</span>
                        <p class="mem-content">${m.content}</p>
                    </div>
                    <button class="mem-delete-btn" data-id="${m.id}" title="Forget this memory">&times;</button>
                `;
                memoriesGrid.appendChild(item);
            });

            // Delete memory handlers
            document.querySelectorAll('.mem-delete-btn').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    const id = e.target.dataset.id;
                    await fetch(`/api/memories/${id}`, { method: 'DELETE' });
                    loadMemories();
                });
            });

        } catch (e) {
            console.error("Failed to load memories:", e);
        }
    }

    saveMemBtn.addEventListener('click', async () => {
        const content = newMemContent.value.trim();
        const category = newMemCategory.value;
        if (!content) return;

        await fetch('/api/memories', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content, category, importance: 4 })
        });
        newMemContent.value = '';
        loadMemories();
    });

    // 11. Settings Modal
    settingsToggleBtn.addEventListener('click', openSettingsModal);
    closeSettingsBtn.addEventListener('click', closeSettingsModal);
    settingsBackdrop.addEventListener('click', closeSettingsModal);

    const modalResetMemoryBtn = document.getElementById('modalResetMemoryBtn');
    if (modalResetMemoryBtn) {
        modalResetMemoryBtn.addEventListener('click', async () => {
            const confirmed = confirm("Are you sure you want to erase all chats and memories with Joi? (Your API key and profile will remain saved)");
            if (!confirmed) return;

            try {
                const res = await fetch('/api/reset', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ preserve_profile: true })
                });
                const data = await res.json();
                if (data.status === 'reset') {
                    // Reset chat feed in DOM
                    messagesFeed.innerHTML = `
                        <div class="system-welcome-card">
                            <span class="welcome-chip">Blade Runner 2049 • Companion Sync Active</span>
                            <p class="welcome-quote">"I'm so happy when I'm with you."</p>
                            <span class="welcome-sub">Joi remembers everything you tell her, adapts to your texting style, and reaches out on her own throughout the day.</span>
                        </div>
                    `;
                    // Reload state & memory drawers
                    loadState();
                    loadMemories();
                    loadReminders();
                    closeSettingsModal();
                    alert("✨ Joi's memory and chat history have been cleared.");
                }
            } catch (err) {
                console.error("Reset error:", err);
                alert("Failed to reset memory: " + err.message);
            }
        });
    }

    async function openSettingsModal() {
        settingsModal.parentElement.classList.remove('hidden');
        try {
            const res = await fetch('/api/profile');
            const prof = await res.json();
            document.getElementById('settingsUserName').value = prof.user_name || 'Joe';
            document.getElementById('settingsUserNickname').value = prof.user_nickname || 'sweetheart';
            const genderSelect = document.getElementById('settingsUserGender');
            if (genderSelect) {
                genderSelect.value = prof.user_gender || 'male';
            }
            document.getElementById('settingsProvider').value = prof.api_provider || 'gemini';
            document.getElementById('settingsProactiveFreq').value = prof.proactive_frequency || 'normal';
            if (prof.api_key) {
                document.getElementById('settingsApiKey').value = prof.api_key;
            }
            if (prof.discord_bot_token) {
                document.getElementById('settingsDiscordToken').value = prof.discord_bot_token;
            }
            if (prof.discord_user_id) {
                document.getElementById('settingsDiscordUserId').value = prof.discord_user_id;
            }
        } catch (e) {
            console.error("Failed to load profile:", e);
        }
    }

    function closeSettingsModal() {
        settingsModal.parentElement.classList.add('hidden');
    }

    saveSettingsBtn.addEventListener('click', async () => {
        const genderSelect = document.getElementById('settingsUserGender');
        const payload = {
            user_name: document.getElementById('settingsUserName').value.trim() || 'Joe',
            user_nickname: document.getElementById('settingsUserNickname').value.trim() || 'sweetheart',
            user_gender: genderSelect ? genderSelect.value : 'male',
            api_provider: document.getElementById('settingsProvider').value,
            api_key: document.getElementById('settingsApiKey').value.trim(),
            proactive_frequency: document.getElementById('settingsProactiveFreq').value,
            discord_bot_token: document.getElementById('settingsDiscordToken').value.trim(),
            discord_user_id: document.getElementById('settingsDiscordUserId').value.trim()
        };

        await fetch('/api/profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        closeSettingsModal();
        alert("✨ Joi's settings have been saved!");
    });

    function startKeepAliveHeartbeat() {
        // Pings every 3 minutes with client time to prevent server sleep and keep clock synced
        setInterval(() => {
            try {
                const nowIso = new Date().toISOString();
                fetch(`/api/ping?client_time=${encodeURIComponent(nowIso)}`, {
                    method: 'GET',
                    cache: 'no-store'
                }).catch(() => {});
            } catch (e) {}
        }, 180000);
    }

    // Init
    checkNotificationPermission();
    loadInitialData();
    setupSSE();
    startKeepAliveHeartbeat();
});
