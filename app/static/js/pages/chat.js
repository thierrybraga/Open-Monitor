class ChatManager {
    constructor() {
        this.sessions = [];
        this.state = {
            isSending: false,
            messageQueue: [],
            lastActivity: Date.now()
        };
        // Prefer IDs from chat.html, fallback to legacy ones
        this.messageInput = document.getElementById('messageInput') || document.getElementById('chat-input');
        this.sendBtn = document.getElementById('sendBtn') || document.getElementById('send-btn');
        this.chatSessions = document.getElementById('chatSessions') || document.getElementById('chat-sessions-list');
        this.chatMessages = document.getElementById('chatMessages') || document.getElementById('chat-messages');
        this.charCount = document.getElementById('charCount') || document.getElementById('char-count');
        this.attachmentInput = null;
        this.attachments = null;
        this.attachmentsPreview = null;
        this.editingSessionId = null;
        this.sessionToDelete = null;

        // Form element
        this.chatForm = document.getElementById('chatForm');

        // Initialize textarea state
        if (this.messageInput) {
            this.autoResizeTextarea();
            this.updateCharCount();
        }

        // Bind form submit to send handler
        if (this.chatForm) {
            this.chatForm.addEventListener('submit', (e) => this.handleSendMessage(e));
        }

        // Bind send button click
        if (this.sendBtn) {
            this.sendBtn.addEventListener('click', (e) => {
                if (this.chatForm) {
                    // Trigger form submission to reuse same flow
                    this.chatForm.dispatchEvent(new Event('submit', { cancelable: true }));
                } else {
                    this.handleSendMessage(e);
                }
            });
        }

        // Bind input events for textarea
        if (this.messageInput) {
            this.messageInput.addEventListener('input', () => {
                this.updateCharCount();
                this.autoResizeTextarea();
            });
            this.messageInput.addEventListener('keydown', (e) => this.handleKeyDown(e));
        }

        // Quick action buttons delegation
        document.addEventListener('click', (e) => {
            const quickBtn = e.target.closest('.quick-action-btn');
            if (quickBtn && quickBtn.dataset && quickBtn.dataset.message) {
                this.sendQuickMessage(quickBtn.dataset.message, e);
            }
        });
    }

    showAttachmentsPreview() {
        try {
            const form = document.getElementById('chatForm');
            if (!form) return;

            if (!this.attachmentsPreview) {
                this.attachmentsPreview = document.createElement('div');
                this.attachmentsPreview.id = 'attachmentsPreview';
                this.attachmentsPreview.className = 'attachments-preview';
                const inputContainer = form.querySelector('.input-container');
                if (inputContainer && inputContainer.parentNode) {
                    inputContainer.parentNode.insertBefore(this.attachmentsPreview, inputContainer.nextSibling);
                } else {
                    form.appendChild(this.attachmentsPreview);
                }
            }

            const items = (this.attachments || []).map((att, index) => `
                <div class="attachment-item">
                    <i class="bi bi-paperclip"></i>
                    <span class="name" title="${this.escapeHtml(att.name)}">${this.escapeHtml(att.name)}</span>
                    <span class="size">${(att.size / 1024).toFixed(1)} KB</span>
                    <button type="button" class="btn btn-sm btn-outline-danger remove-attachment" data-index="${index}" aria-label="Remover anexo">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
            `).join('');

            this.attachmentsPreview.innerHTML = `
                <div class="attachments-header">
                    <span>${(this.attachments || []).length} anexo(s)</span>
                    ${this.attachments && this.attachments.length ? '<button type="button" class="btn btn-sm btn-outline-secondary" id="clear-attachments-btn">Limpar</button>' : ''}
                </div>
                <div class="attachments-list">
                    ${items || '<div class="no-attachments">Nenhum anexo selecionado</div>'}
                </div>
            `;

            this.attachmentsPreview.querySelectorAll('.remove-attachment').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const idx = parseInt(e.currentTarget.getAttribute('data-index'), 10);
                    this.removeAttachment(idx);
                });
            });

            const clearBtn = this.attachmentsPreview.querySelector('#clear-attachments-btn');
            if (clearBtn) {
                clearBtn.addEventListener('click', () => this.clearAttachments());
            }
        } catch (err) {
            console.error(err);
        }
    }

    removeAttachment(index) {
        if (!this.attachments) return;
        this.attachments.splice(index, 1);
        this.showAttachmentsPreview();
    }

    clearAttachments() {
        this.attachments = [];
        if (this.attachmentsPreview) {
            this.attachmentsPreview.innerHTML = '';
        }
        if (this.attachmentInput) {
            this.attachmentInput.value = '';
        }
    }

    buildAttachmentMetadata() {
        if (!this.attachments || this.attachments.length === 0) return null;
        return {
            attachments: this.attachments.map(att => ({
                name: att.name,
                size: att.size,
                type: att.type
            }))
        };
    }

    exportChat() {
        if (!this.currentSessionId) {
            this.showNotification('Selecione uma conversa para exportar', 'warning');
            return;
        }
        try {
            const session = this.sessions.find(s => s.id === this.currentSessionId) || {};
            fetch(`/api/chat/sessions/${this.currentSessionId}/messages`)
                .then(res => res.json())
                .then(data => {
                    const messages = Array.isArray(data.messages) ? data.messages : [];
                    const exportData = {
                        session: {
                            id: session.id || this.currentSessionId,
                            title: session.title || 'Sem título',
                            created_at: session.created_at || null,
                            last_activity: session.last_activity || null,
                            message_count: messages.length
                        },
                        messages: messages.map(m => {
                            let metadataObj = null;
                            if (m.metadata) {
                                try { metadataObj = JSON.parse(m.metadata); } catch (e) { metadataObj = m.metadata; }
                            }
                            return {
                                id: m.id,
                                type: (m.message_type || '').toString().toLowerCase(),
                                content: m.content,
                                metadata: metadataObj,
                                token_count: m.token_count,
                                processing_time: m.processing_time,
                                created_at: m.created_at,
                                updated_at: m.updated_at,
                                is_edited: m.is_edited,
                                is_deleted: m.is_deleted
                            };
                        })
                    };
                    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    const fileName = `chat-${this.currentSessionId}-${new Date().toISOString().slice(0,10)}.json`;
                    a.href = url;
                    a.download = fileName;
                    document.body.appendChild(a);
                    a.click();
                    setTimeout(() => {
                        URL.revokeObjectURL(url);
                        document.body.removeChild(a);
                    }, 0);
                    this.showNotification('Conversa exportada', 'success');
                })
                .catch(err => {
                    console.error(err);
                    this.showNotification('Erro ao exportar conversa', 'error');
                });
        } catch (err) {
            console.error(err);
            this.showNotification('Erro ao exportar conversa', 'error');
        }
    }

    handleVisibilityChange() {
        if (document.hidden) {
            this.saveState();
        } else {
            this.state.lastActivity = Date.now();
        }
    }

    handleInactivity() {
        // Implementar acoes para inatividade prolongada
        console.log('Usuario inativo por mais de 5 minutos');
    }

    saveState() {
        // Salvar estado da aplicacao no localStorage
        const state = {
            currentSessionId: this.currentSessionId,
            lastActivity: this.state.lastActivity,
            inputValue: this.messageInput.value
        };
        localStorage.setItem('chatState', JSON.stringify(state));
    }

    restoreState() {
        // Restaurar estado da aplicacao
        const savedState = localStorage.getItem('chatState');
        if (savedState) {
            try {
                const state = JSON.parse(savedState);
                if (state.inputValue) {
                    this.messageInput.value = state.inputValue;
                    this.updateCharCount();
                    this.autoResizeTextarea();
                }
            } catch (error) {
                console.error('Erro ao restaurar estado:', error);
            }
        }
    }

    autoResizeTextarea() {
        const textarea = this.messageInput;
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    }

    updateCharCount() {
        const count = this.messageInput.value.length;
        
        // Verificação de segurança para evitar erro se charCount for null
        if (this.charCount) {
            this.charCount.textContent = count;
            
            if (count > 3800) {
                this.charCount.style.color = '#dc3545';
            } else if (count > 3500) {
                this.charCount.style.color = '#ffc107';
            } else {
                this.charCount.style.color = '#6c757d';
            }
        }
    }

    handleKeyDown(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            this.handleSendMessage(e);
        }
    }

    async loadSessions() {
        try {
            // Mostrar loading na lista de sessoes
            if (this.chatSessions) {
                this.chatSessions.innerHTML = `
                    <div class="loading-sessions">
                        <div class="loading-spinner"></div>
                        <span>Carregando conversas...</span>
                    </div>
                `;
            }
            
            const response = await fetch('/api/chat/sessions');
            if (response.ok) {
                const data = await response.json();
                this.sessions = data.sessions || [];
                this.renderSessions();
            } else {
                throw new Error('Erro ao carregar sessoes');
            }
        } catch (error) {
            console.error('Erro ao carregar sessoes:', error);
            if (this.chatSessions) {
                this.chatSessions.innerHTML = `
                    <div class="error-message">
                        <i class="bi bi-exclamation-triangle"></i>
                        <span>Erro ao carregar conversas</span>
                        <button onclick="chatManager.loadSessions()" class="btn-retry">
                            <i class="bi bi-arrow-clockwise"></i>
                            Tentar novamente
                        </button>
                    </div>
                `;
            } else {
                console.error('Elemento chatSessions nao encontrado');
            }
        }
    }

    showSessionsLoading(show) {
        const loadingElement = document.querySelector('.loading-sessions');
        const sessionsList = document.getElementById('chat-sessions-list');
        
        if (show) {
            loadingElement.style.display = 'flex';
        } else {
            loadingElement.style.display = 'none';
        }
    }

    renderSessions() {
        if (!this.chatSessions) {
            console.error('Elemento chatSessions nao encontrado');
            return;
        }
        
        if (this.sessions.length === 0) {
            this.chatSessions.innerHTML = `
                <div class="no-sessions">
                    <div style="text-align: center; padding: 40px 20px; color: var(--text-muted);">
                        <i class="bi bi-chat-dots fa-2x mb-3" style="color: var(--primary-color);"></i>
                        <p>Nenhuma conversa ainda</p>
                        <small>Comece uma nova conversa para comecar</small>
                    </div>
                </div>
            `;
            return;
        }
        
        // Criar elementos com animacao
        this.chatSessions.innerHTML = '';
        
        this.sessions.forEach((session, index) => {
            const sessionElement = document.createElement('div');
            sessionElement.className = `chat-session-item ${session.id === this.currentSessionId ? 'active' : ''}`;
            sessionElement.dataset.sessionId = session.id;
            sessionElement.style.animationDelay = `${index * 0.1}s`;
            
            const lastActivity = new Date(session.last_activity);
            const timeAgo = this.getTimeAgo(lastActivity);
            
            sessionElement.innerHTML = `
                <div class="chat-session-content">
                    <div class="session-header">
                        <div class="session-header-left">
                            <div class="chat-session-title">${this.escapeHtml(session.title || 'Nova Conversa')}</div>
                            <div class="chat-session-time">${timeAgo}</div>
                        </div>
                        <div class="session-header-right">
                            <div class="session-dropdown">
                                <button class="btn-session-menu" onclick="event.stopPropagation(); chatManager.toggleSessionDropdown(${session.id})" title="Mais opções">
                                    <i class="bi bi-three-dots-vertical"></i>
                                </button>
                                <div class="session-dropdown-menu" id="dropdown-${session.id}">
                                    <button class="dropdown-item" onclick="event.stopPropagation(); chatManager.showEditTitleModal(${session.id})">
                                        <i class="bi bi-pencil"></i>
                                        Editar título
                                    </button>
                                    <button class="dropdown-item" onclick="event.stopPropagation(); chatManager.archiveSession(${session.id})">
                                        <i class="bi bi-archive"></i>
                                        Arquivar
                                    </button>
                                    <button class="dropdown-item delete-item" onclick="event.stopPropagation(); chatManager.showDeleteModal(${session.id})">
                                        <i class="bi bi-trash"></i>
                                        Excluir
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="session-preview">${this.escapeHtml(session.preview || 'Sem mensagens ainda')}</div>
                </div>
                <div class="session-indicator"></div>
            `;
            
            // Adicionar event listener para carregar sessao
            sessionElement.addEventListener('click', (e) => {
                if (!e.target.closest('.btn-session-action')) {
                    const sessionId = parseInt(sessionElement.dataset.sessionId);
                    this.selectSessionWithAnimation(sessionId, sessionElement);
                }
            });
            
            // Adicionar efeitos hover
            sessionElement.addEventListener('mouseenter', () => {
                if (!sessionElement.classList.contains('active') && sessionElement.style) {
                    sessionElement.style.transform = 'translateX(4px)';
                }
            });
            
            sessionElement.addEventListener('mouseleave', () => {
                if (!sessionElement.classList.contains('active') && sessionElement.style) {
                    sessionElement.style.transform = '';
                }
            });
            
            this.chatSessions.appendChild(sessionElement);
        });
        
        // Trigger animation
        requestAnimationFrame(() => {
            this.chatSessions.classList.add('sessions-loaded');
        });
    }

    animateSessionsIn(container) {
        const items = container.querySelectorAll('.chat-session-item');
        items.forEach((item, index) => {
            if (item && item.style) {
                item.style.opacity = '0';
                item.style.transform = 'translateX(-20px)';
                item.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                
                setTimeout(() => {
                    if (item && item.style) {
                        item.style.opacity = '1';
                        item.style.transform = 'translateX(0)';
                    }
                }, index * 50);
            }
        });
    }

    async selectSessionWithAnimation(sessionId, element) {
        if (this.currentSessionId === sessionId) return;

        // Animar selecao
        if (element && element.style) {
            element.style.transform = 'scale(0.98)';
            setTimeout(() => {
                if (element && element.style) {
                    element.style.transform = '';
                }
            }, 150);
        }

        await this.selectSession(sessionId);
    }

    async createNewSession() {
        try {
            // Adicionar animacao de clique no botao
            const newChatBtn = document.getElementById('new-chat-btn');
            if (newChatBtn) {
                newChatBtn.style.transform = 'scale(0.95)';
                setTimeout(() => {
                    newChatBtn.style.transform = '';
                }, 150);
            }
            
            // Verificar se ja estamos em uma nova conversa vazia
            if (!this.currentSessionId && this.chatMessages.children.length <= 1) {
                this.messageInput?.focus();
                return;
            }
            
            // Animar saida das mensagens atuais
            const currentMessages = this.chatMessages.querySelectorAll('.message');
            if (currentMessages.length > 0) {
                currentMessages.forEach((msg, index) => {
                    setTimeout(() => {
                        if (msg && msg.style) {
                            msg.style.opacity = '0';
                            msg.style.transform = 'translateY(-20px) scale(0.9)';
                        }
                    }, index * 30);
                });
                
                // Aguardar animacao
                await new Promise(resolve => setTimeout(resolve, currentMessages.length * 30 + 300));
            }
            
            const response = await fetch('/api/chat/sessions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    title: 'Nova Conversa'
                })
            });

            const data = await response.json();

            if (data.success) {
                this.sessions.unshift(data.session);
                this.renderSessions();
                this.selectSession(data.session.id);
                this.showNotification('Nova conversa criada', 'success');
                
                // Reset state
                this.state.isSending = false;
                this.state.messageQueue = [];
                
                // Limpar input e focar
                this.messageInput.value = '';
                this.updateCharCount();
                this.autoResizeTextarea();
                
                // Focus input apos pequeno delay
                setTimeout(() => {
                    this.messageInput.focus();
                }, 100);
            } else {
                this.showNotification('Erro ao criar conversa', 'error');
            }
        } catch (error) {
            console.error('Erro ao criar sessao:', error);
            this.showNotification('Erro ao criar conversa', 'error');
        }
    }

    sendQuickMessage(message, event = null) {
        // Animar botao clicado
        if (event) {
            const clickedBtn = event.target.closest('.quick-action-btn');
            if (clickedBtn) {
                clickedBtn.style.transform = 'scale(0.95)';
                setTimeout(() => {
                    clickedBtn.style.transform = '';
                }, 150);
            }
        }
        
        // Definir mensagem no input e enviar
        this.messageInput.value = message;
        this.updateCharCount();
        this.autoResizeTextarea();
        
        // Enviar mensagem apos pequeno delay para melhor UX
        setTimeout(() => {
            this.handleSendMessage(new Event('submit'));
        }, 200);
    }

    async selectSession(sessionId) {
        if (this.currentSessionId === sessionId) return;

        this.currentSessionId = sessionId;
        const session = this.sessions.find(s => s.id === sessionId);
        
        if (!session) return;

        // Update UI
        this.updateChatHeader(session);
        this.renderSessions(); // Re-render to update active state
        
        // Load messages
        await this.loadMessages(sessionId);
        
        // Show input area
        const inputArea = document.getElementById('chat-input-area');
        if (inputArea) {
            inputArea.style.display = 'block';
        }
        
        // Focus on input
        this.messageInput.focus();
    }

    updateChatHeader(session) {
        const titleElement = document.getElementById('current-chat-title');
        const editBtn = document.getElementById('edit-title-btn');
        const deleteBtn = document.getElementById('delete-chat-btn');
        
        if (titleElement) {
            titleElement.textContent = session.title;
        }
        if (editBtn) {
            editBtn.style.display = 'inline-block';
        }
        if (deleteBtn) {
            deleteBtn.style.display = 'inline-block';
        }
    }

    async loadMessages(sessionId) {
        try {
            const response = await fetch(`/api/chat/sessions/${sessionId}/messages`);
            const data = await response.json();

            if (data.success) {
                this.renderMessages(data.messages);
            } else {
                this.showNotification('Erro ao carregar mensagens', 'error');
            }
        } catch (error) {
            console.error('Erro ao carregar mensagens:', error);
            this.showNotification('Erro ao carregar mensagens', 'error');
        }
    }

    renderMessages(messages) {
        if (messages.length === 0) {
            this.chatMessages.innerHTML = `
                <div class="welcome-message fade-in">
                    <div class="welcome-content">
                        <div class="welcome-icon">
                            <i class="bi bi-robot"></i>
                        </div>
                        <h3 class="welcome-title">Bem-vindo ao Open Monitor AI</h3>
                        <p class="welcome-subtitle">Como posso ajuda-lo hoje? Voce pode fazer perguntas sobre monitoramento, analise de dados ou qualquer outro topico.</p>
                        
                        <div class="quick-actions">
                            <button class="quick-action-btn" data-message="Como funciona o monitoramento?" aria-label="Enviar ação rápida: Como funciona?">
                                <i class="bi bi-question-circle"></i>
                                Como funciona?
                            </button>
                            <button class="quick-action-btn" data-message="Mostrar estatisticas do sistema" aria-label="Enviar ação rápida: Estatísticas">
                                <i class="bi bi-graph-up"></i>
                                Estatisticas
                            </button>
                            <button class="quick-action-btn" data-message="Configurar alertas" aria-label="Enviar ação rápida: Alertas">
                                <i class="bi bi-bell"></i>
                                Alertas
                            </button>
                            <button class="quick-action-btn" data-message="Ajuda com comandos" aria-label="Enviar ação rápida: Comandos">
                                <i class="bi bi-terminal"></i>
                                Comandos
                            </button>
                        </div>
                    </div>
                </div>
            `;
            // Vincular eventos aos botões de ações rápidas
            this.setupQuickActions();
            return;
        }

        const messagesHtml = messages.map(message => this.createMessageHtml(message)).join('');
        this.chatMessages.innerHTML = messagesHtml;
        this.scrollToBottom();
    }

    createMessageHtml(message) {
        const messageTime = new Date(message.created_at);
        const timeString = messageTime.toLocaleTimeString('pt-BR', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });

        const type = (message.message_type || '').toString().toLowerCase();
        const avatarContent = type === 'user' ? 'U' : 'AI';
        const messageClass = type || 'assistant';

        return `
            <div class="message ${messageClass}" data-message-id="${message.id}">
                <div class="message-avatar">${avatarContent}</div>
                <div class="message-content">
                    <div class="message-bubble">
                        ${this.formatMessageContent(message.content)}
                    </div>
                    <div class="message-time">${timeString}${message.is_edited ? ' · editada' : ''}</div>
                    ${type === 'user' ? this.createMessageActions(message) : ''}
                </div>
            </div>
        `;
    }

    createMessageActions(message) {
        return `
            <div class="message-actions">
                <button class="btn btn-sm" onclick="chatManager.editMessage(${message.id})" title="Editar">
                    <i class="fas fa-edit"></i>
                </button>
                <button class="btn btn-sm" onclick="chatManager.deleteMessage(${message.id})" title="Excluir">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `;
    }

    formatMessageContent(content) {
        // Basic formatting - convert line breaks to <br>
        return this.escapeHtml(content).replace(/\n/g, '<br>');
    }

    async handleSendMessage(e) {
        e.preventDefault();
        
        const content = this.messageInput.value.trim();
        if (!content || this.state.isSending) return;

        // Se não há sessão selecionada, criar uma nova automaticamente
        if (!this.currentSessionId) {
            try {
                await this.createNewSession();
                // Aguardar um pouco para garantir que a sessão foi criada
                await new Promise(resolve => setTimeout(resolve, 100));
            } catch (error) {
                this.showNotification('Erro ao criar nova conversa', 'error');
                return;
            }
        }

        // Set sending state
        this.state.isSending = true;
        this.setFormEnabled(false);
        
        try {
            // Add user message to UI immediately with animation
            const userMessage = {
                id: Date.now(), // Temporary ID
                content: content,
                message_type: 'user',
                created_at: new Date().toISOString()
            };
            
            this.addMessageToUI(userMessage);
            this.messageInput.value = '';
            this.updateCharCount();
            this.autoResizeTextarea();
            
            // Show enhanced typing indicator
            this.showTypingIndicator();

            const metadata = this.buildAttachmentMetadata();

            // Send to server
            const response = await fetch(`/api/chat/sessions/${this.currentSessionId}/messages`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ content, metadata })
            });

            const data = await response.json();

            if (data.success) {
                // Add assistant response
                this.addMessageToUI(data.assistant_message);
                // Update session in list
                this.updateSessionLastActivity(this.currentSessionId);
                this.showNotification('Mensagem enviada', 'success');
            } else {
                this.showNotification(data.error || 'Erro ao enviar mensagem', 'error');
            }
        } catch (error) {
            console.error('Erro ao enviar mensagem:', error);
            this.showNotification('Erro ao enviar mensagem', 'error');
        } finally {
            this.hideTypingIndicator();
            this.state.isSending = false;
            this.setFormEnabled(true);
            this.messageInput.focus();
            this.clearAttachments();
        }
    }

    async simulateTypingDelay(message) {
        // Simular tempo de digitacao baseado no tamanho da mensagem
        const baseDelay = 800;
        const charDelay = message.length * 15;
        const totalDelay = Math.min(baseDelay + charDelay, 2500);
        
        return new Promise(resolve => setTimeout(resolve, totalDelay));
    }

    addMessageToUI(message) {
        const welcomeMessage = this.chatMessages.querySelector('.welcome-message');
        if (welcomeMessage) {
            welcomeMessage.style.display = 'none';
        }

        const id = message.id || Date.now();
        const type = (message.message_type || 'assistant').toString().toLowerCase();
        const timestamp = new Date(message.created_at || Date.now()).toLocaleTimeString('pt-BR', {
            hour: '2-digit',
            minute: '2-digit'
        });

        const html = `
            <div class="message ${type}" data-message-id="${id}">
                <div class="message-avatar">${type === 'user' ? 'U' : 'AI'}</div>
                <div class="message-content">
                    <div class="message-bubble">
                        ${this.formatMessageContent(message.content || '')}
                    </div>
                    <div class="message-time">${timestamp}</div>
                </div>
            </div>
        `;

        this.chatMessages.insertAdjacentHTML('beforeend', html);
        this.scrollToBottom();
    }

    animateMessageIn(element) {
        if (element && element.style) {
            element.style.opacity = '0';
            element.style.transform = 'translateY(20px)';
            element.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
            
            requestAnimationFrame(() => {
                if (element && element.style) {
                    element.style.opacity = '1';
                    element.style.transform = 'translateY(0)';
                }
            });
        }
    }

    fadeOutElement(element) {
        if (element && element.style) {
            element.style.transition = 'opacity 0.3s ease';
            element.style.opacity = '0';
        }
        
        setTimeout(() => {
            if (element.parentNode) {
                element.remove();
            }
        }, 300);
    }

    showTypingIndicator() {
        if (document.querySelector('.typing-indicator')) return;

        const typingHtml = `
            <div class="message assistant typing-indicator">
                <div class="message-avatar">AI</div>
                <div class="message-content">
                    <div class="message-bubble">
                        <div class="typing-dots">
                            <div class="typing-dot"></div>
                            <div class="typing-dot"></div>
                            <div class="typing-dot"></div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        this.chatMessages.insertAdjacentHTML('beforeend', typingHtml);
        this.scrollToBottom();
    }

    hideTypingIndicator() {
        const typingIndicator = document.querySelector('.typing-indicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
    }

    setFormEnabled(enabled) {
        this.messageInput.disabled = !enabled;
        this.sendBtn.disabled = !enabled;
        
        if (enabled) {
            this.sendBtn.innerHTML = '<i class="bi bi-send"></i>';
        } else {
            this.sendBtn.innerHTML = '<i class="bi bi-arrow-clockwise"></i>';
        }
    }

    updateSessionLastActivity(sessionId) {
        const session = this.sessions.find(s => s.id === sessionId);
        if (session) {
            session.last_activity = new Date().toISOString();
            
            // Move to top of list
            this.sessions = this.sessions.filter(s => s.id !== sessionId);
            this.sessions.unshift(session);
            this.renderSessions();
        }
    }

    scrollToBottom() {
        setTimeout(() => {
            this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
        }, 100);
    }

    showEditTitleModal(sessionId = null) {
        const targetSessionId = sessionId || this.currentSessionId;
        if (!targetSessionId) return;
        
        const session = this.sessions.find(s => s.id === targetSessionId);
        if (!session) return;
        
        // Store the session ID for later use in saveTitle
        this.editingSessionId = targetSessionId;
        
        document.getElementById('new-title').value = session.title;
    const modal = window.getModalInstance(document.getElementById('edit-title-modal'));
        modal.show();
    }

    async saveTitle() {
        const newTitle = document.getElementById('new-title').value.trim();
        const targetSessionId = this.editingSessionId || this.currentSessionId;
        if (!newTitle || !targetSessionId) return;

        try {
            const response = await fetch(`/api/chat/sessions/${targetSessionId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ title: newTitle })
            });

            const data = await response.json();

            if (data.success) {
                // Update local data
                const session = this.sessions.find(s => s.id === targetSessionId);
                if (session) {
                    session.title = newTitle;
                    // Only update chat header if editing current session
                    if (targetSessionId === this.currentSessionId) {
                        this.updateChatHeader(session);
                    }
                    this.renderSessions();
                }
                
                // Close modal
                const modal = bootstrap.Modal.getInstance(document.getElementById('edit-title-modal'));
                modal.hide();
                
                this.showNotification('Titulo atualizado', 'success');
            } else {
                this.showNotification('Erro ao atualizar titulo', 'error');
            }
        } catch (error) {
            console.error('Erro ao salvar titulo:', error);
            this.showNotification('Erro ao atualizar titulo', 'error');
        }
    }

    showDeleteModal(sessionId = null) {
        // Use o sessionId passado ou o currentSessionId
        const targetSessionId = sessionId || this.currentSessionId;
        if (!targetSessionId) return;
        
        // Armazenar o ID da sessão a ser deletada
        this.sessionToDelete = targetSessionId;
        
    const modal = window.getModalInstance(document.getElementById('delete-chat-modal'));
        modal.show();
    }

    async deleteSession() {
        const sessionIdToDelete = this.sessionToDelete || this.currentSessionId;
        if (!sessionIdToDelete) return;

        try {
            const response = await fetch(`/api/chat/sessions/${sessionIdToDelete}`, {
                method: 'DELETE'
            });

            const data = await response.json();

            if (data.success) {
                // Remove from local data
                this.sessions = this.sessions.filter(s => s.id !== sessionIdToDelete);
                
                // Se a sessão deletada era a atual, resetar UI
                if (sessionIdToDelete === this.currentSessionId) {
                    this.currentSessionId = null;
                    this.resetChatArea();
                }
                
                this.renderSessions();
                
                // Close modal
                const modal = bootstrap.Modal.getInstance(document.getElementById('delete-chat-modal'));
                modal.hide();
                
                // Limpar a variável
                this.sessionToDelete = null;
                
                this.showNotification('Conversa excluída', 'success');
            } else {
                this.showNotification('Erro ao excluir conversa', 'error');
            }
        } catch (error) {
            console.error('Erro ao deletar conversa:', error);
            this.showNotification('Erro ao excluir conversa', 'error');
        }
    }

    resetChatArea() {
        const titleElement = document.getElementById('current-chat-title');
        const editBtn = document.getElementById('edit-title-btn');
        const deleteBtn = document.getElementById('delete-chat-btn');
        const inputArea = document.getElementById('chat-input-area');
        
        if (titleElement) {
            titleElement.textContent = 'Selecione uma conversa';
        }
        if (editBtn) {
            editBtn.style.display = 'none';
        }
        if (deleteBtn) {
            deleteBtn.style.display = 'none';
        }
        if (inputArea) {
            inputArea.style.display = 'none';
        }
        
        this.chatMessages.innerHTML = `
            <div class="welcome-message">
                <div class="welcome-content">
                    <i class="fas fa-comments fa-3x text-primary mb-3"></i>
                    <h5>Bem-vindo ao Chat do Open Monitor</h5>
                    <p class="text-muted">Selecione uma conversa existente ou inicie uma nova para comecar.</p>
                </div>
            </div>
        `;
    }

    showNotification(message, type = 'info') {
        if (window.safeNotify) {
            window.safeNotify(type, null, message, 3000);
            return;
        }
        try {
            const toast = document.getElementById('notification-toast');
            const toastMessage = document.getElementById('toast-message');
            const toastHeader = toast ? toast.querySelector('.toast-header i') : null;
            if (!toast || !toastMessage) throw new Error('notification-toast not found');
            if (toastHeader) {
                toastHeader.className = `fas me-2 ${this.getToastIcon(type)} ${this.getToastColor(type)}`;
            }
            toastMessage.textContent = message;
            const bsToast = window.getToastInstance ? window.getToastInstance(toast) : (window.bootstrap && window.bootstrap.Toast ? new window.bootstrap.Toast(toast) : null);
            if (bsToast && bsToast.show) { bsToast.show(); }
            else if (toast && toast.classList) { toast.classList.add('show'); setTimeout(() => toast.classList.remove('show'), 3000); }
        } catch (e) {
            if (window.showSystemAlert) window.showSystemAlert(message, type === 'error' ? 'danger' : type, 3000);
            else console.warn('Notification:', type, message);
        }
    }

    showWelcomeMessage() {
        const welcomeHtml = `
            <div class="welcome-message fade-in">
                <div class="welcome-content">
                    <div class="welcome-icon">
                        <i class="bi bi-chat-heart"></i>
                    </div>
                    <h3>Bem-vindo ao Chat!</h3>
                    <p>Como posso ajuda-lo hoje? Digite sua mensagem abaixo para comecar nossa conversa.</p>
                    <div class="quick-actions">
                        <button class="quick-action-btn" data-message="Ola! Como voce pode me ajudar?" aria-label="Enviar ação rápida: Cumprimentar">
                            <i class="bi bi-hand-thumbs-up"></i>
                            Cumprimentar
                        </button>
                        <button class="quick-action-btn" data-message="Preciso de ajuda com um problema" aria-label="Enviar ação rápida: Pedir Ajuda">
                            <i class="bi bi-question-circle"></i>
                            Pedir Ajuda
                        </button>
                        <button class="quick-action-btn" data-message="Quais sao suas funcionalidades?" aria-label="Enviar ação rápida: Funcionalidades">
                            <i class="bi bi-info-circle"></i>
                            Funcionalidades
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        this.chatMessages.innerHTML = welcomeHtml;
    }

    getToastIcon(type) {
        const icons = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };
        return icons[type] || icons.info;
    }

    getToastColor(type) {
        const colors = {
            success: 'text-success',
            error: 'text-danger',
            warning: 'text-warning',
            info: 'text-primary'
        };
        return colors[type] || colors.info;
    }

    getTimeAgo(date) {
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) return 'Agora';
        if (diffMins < 60) return `${diffMins}m`;
        if (diffHours < 24) return `${diffHours}h`;
        if (diffDays < 7) return `${diffDays}d`;
        
        return date.toLocaleDateString('pt-BR', { 
            day: '2-digit', 
            month: '2-digit' 
        });
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    formatDate(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diff = now - date;
        
        if (diff < 60000) return 'Agora';
        if (diff < 3600000) return `${Math.floor(diff / 60000)}m`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)}h`;
        if (diff < 604800000) return `${Math.floor(diff / 86400000)}d`;
        
        return date.toLocaleDateString('pt-BR');
    }

    // Message actions
    async editMessage(messageId) {
        const messageEl = this.chatMessages.querySelector(`.message[data-message-id="${messageId}"]`);
        if (!messageEl) {
            this.showNotification('Mensagem não encontrada', 'warning');
            return;
        }
        const contentEl = messageEl.querySelector('.message-bubble, .message-text');
        const currentContent = contentEl ? contentEl.textContent : '';
        const textareaHtml = `
            <div class="edit-message-form">
                <label class="form-label">Editar mensagem</label>
                <textarea id="edit-message-input" class="form-control" rows="4">${this.escapeHtml(currentContent)}</textarea>
            </div>
        `;
        this.createModal({
            title: 'Editar mensagem',
            content: textareaHtml,
            actions: [
                { label: 'Cancelar', class: 'btn btn-secondary', onClick: () => this.closeModal() },
                { label: 'Salvar', class: 'btn btn-primary', onClick: async () => {
                    const input = document.getElementById('edit-message-input');
                    const newContent = input ? input.value.trim() : '';
                    if (!newContent) {
                        this.showNotification('Conteúdo é obrigatório', 'warning');
                        return;
                    }
                    try {
                        const response = await fetch(`/api/chat/messages/${messageId}`, {
                            method: 'PUT',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ content: newContent })
                        });
                        const data = await response.json();
                        if (!data.success) {
                            this.showNotification(data.error || 'Erro ao editar mensagem', 'error');
                            return;
                        }
                        if (contentEl) {
                            contentEl.innerHTML = this.formatMessageContent(newContent);
                        }
                        const timeEl = messageEl.querySelector('.message-time');
                        if (timeEl && data.message && data.message.updated_at) {
                            const t = new Date(data.message.updated_at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
                            timeEl.innerHTML = `${t} · editada`;
                        }
                        this.closeModal();
                        this.showNotification('Mensagem editada', 'success');
                    } catch (err) {
                        this.showNotification('Erro ao salvar edição', 'error');
                        console.error(err);
                    }
                }}
            ]
        });
    }

    async deleteMessage(messageId) {
        if (!confirm('Tem certeza que deseja excluir esta mensagem?')) return;

        try {
            const response = await fetch(`/api/chat/messages/${messageId}`, {
                method: 'DELETE'
            });

            const data = await response.json();

            if (data.success) {
                // Remove message from UI
                const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
                if (messageElement) {
                    messageElement.remove();
                }
                
                this.showNotification('Mensagem excluida', 'success');
            } else {
                this.showNotification('Erro ao excluir mensagem', 'error');
            }
        } catch (error) {
            console.error('Erro ao deletar mensagem:', error);
            this.showNotification('Erro ao excluir mensagem', 'error');
        }
    }

    setupMobileMenu() {
        const mobileMenuToggle = document.getElementById('mobile-menu-toggle');
        const sidebar = document.querySelector('.chat-sidebar');
        const overlay = document.querySelector('.chat-overlay');
        
        if (mobileMenuToggle && sidebar) {
            mobileMenuToggle.addEventListener('click', () => {
                this.toggleMobileMenu();
            });
        }
        
        if (overlay) {
            overlay.addEventListener('click', () => {
                this.closeMobileMenu();
            });
        }
        
        // Close menu when clicking on a session
        document.addEventListener('click', (e) => {
            if (e.target.closest('.chat-session') && window.innerWidth <= 768) {
                this.closeMobileMenu();
            }
        });
    }
    
    toggleMobileMenu() {
        const sidebar = document.querySelector('.chat-sidebar');
        const overlay = document.querySelector('.chat-overlay');
        const body = document.body;
        
        if (sidebar && overlay) {
            const isOpen = sidebar.classList.contains('open');
            
            if (isOpen) {
                this.closeMobileMenu();
            } else {
                this.openMobileMenu();
            }
        }
    }
    
    openMobileMenu() {
        const sidebar = document.querySelector('.chat-sidebar');
        const overlay = document.querySelector('.chat-overlay');
        const body = document.body;
        
        if (sidebar && overlay) {
            sidebar.classList.add('open');
            overlay.classList.add('active');
            body.style.overflow = 'hidden';
        }
    }
    
    closeMobileMenu() {
        const sidebar = document.querySelector('.chat-sidebar');
        const overlay = document.querySelector('.chat-overlay');
        const body = document.body;
        
        if (sidebar && overlay) {
            sidebar.classList.remove('open');
            overlay.classList.remove('active');
            body.style.overflow = '';
        }
    }
    
    handleResize() {
        // Close mobile menu on desktop
        if (window.innerWidth > 768) {
            this.closeMobileMenu();
        }
        
        // Adjust chat messages height
        this.adjustChatHeight();
    }
    
    adjustChatHeight() {
        if (this.chatMessages && this.chatMessages.style) {
            const windowHeight = window.innerHeight;
            const headerHeight = document.querySelector('.chat-header')?.offsetHeight || 0;
            const inputAreaHeight = document.querySelector('.chat-input-area')?.offsetHeight || 0;
            const availableHeight = windowHeight - headerHeight - inputAreaHeight - 40; // 40px for padding
            
            this.chatMessages.style.maxHeight = `${availableHeight}px`;
        }
    }

    // ===== GERENCIAMENTO DE SESSÕES =====

    showDeleteModal(sessionId) {
        const session = this.sessions.find(s => s.id === sessionId);
        if (!session) return;

        const modal = this.createModal({
            title: 'Excluir Conversa',
            content: `
                <div class="delete-modal-content">
                    <div class="warning-icon">
                        <i class="bi bi-exclamation-triangle"></i>
                    </div>
                    <p>Tem certeza que deseja excluir a conversa <strong>"${this.escapeHtml(session.title)}"</strong>?</p>
                    <p class="text-muted">Esta ação não pode ser desfeita.</p>
                </div>
            `,
            actions: [
                {
                    text: 'Cancelar',
                    class: 'btn-secondary',
                    action: () => this.closeModal()
                },
                {
                    text: 'Excluir',
                    class: 'btn-danger',
                    action: () => this.deleteSession(sessionId)
                }
            ]
        });
    }

    async deleteSession(sessionId) {
        try {
            this.closeModal();
            this.showNotification('Excluindo conversa...', 'info');

            const response = await fetch(`/api/chat/sessions/${sessionId}`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const data = await response.json();

            if (data.success) {
                // Remover da lista local
                this.sessions = this.sessions.filter(s => s.id !== sessionId);
                
                // Se era a sessão atual, criar nova
                if (this.currentSessionId === sessionId) {
                    this.currentSessionId = null;
                    this.chatMessages.innerHTML = '';
                    this.showWelcomeMessage();
                }
                
                this.renderSessions();
                this.showNotification('Conversa excluída com sucesso', 'success');
            } else {
                this.showNotification(data.error || 'Erro ao excluir conversa', 'error');
            }
        } catch (error) {
            console.error('Erro ao excluir sessão:', error);
            this.showNotification('Erro ao excluir conversa', 'error');
        }
    }

    showBulkDeleteModal() {
        const modal = this.createModal({
            title: 'Gerenciar Conversas',
            content: `
                <div class="bulk-delete-content">
                    <div class="session-stats">
                        <p>Total de conversas: <strong>${this.sessions.length}</strong></p>
                    </div>
                    
                    <div class="bulk-actions">
                        <h4>Ações em Lote</h4>
                        
                        <div class="action-group">
                            <button class="btn btn-warning" onclick="chatManager.showCleanupModal()">
                                <i class="bi bi-clock-history"></i>
                                Limpar Conversas Antigas
                            </button>
                            <small class="text-muted">Remove conversas com mais de 30 dias</small>
                        </div>
                        
                        <div class="action-group">
                            <button class="btn btn-danger" onclick="chatManager.showSelectDeleteModal()">
                                <i class="bi bi-trash"></i>
                                Excluir Conversas Selecionadas
                            </button>
                            <small class="text-muted">Selecione conversas específicas para excluir</small>
                        </div>
                    </div>
                </div>
            `,
            actions: [
                {
                    text: 'Fechar',
                    class: 'btn-secondary',
                    action: () => this.closeModal()
                }
            ]
        });
    }

    showCleanupModal() {
        const modal = this.createModal({
            title: 'Limpeza Automática',
            content: `
                <div class="cleanup-modal-content">
                    <p>Configure os critérios para limpeza automática de conversas antigas:</p>
                    
                    <div class="form-group">
                        <label for="daysOld">Excluir conversas com mais de:</label>
                        <select id="daysOld" class="form-control">
                            <option value="7">7 dias</option>
                            <option value="15">15 dias</option>
                            <option value="30" selected>30 dias</option>
                            <option value="60">60 dias</option>
                            <option value="90">90 dias</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="keepRecent">Manter as mais recentes:</label>
                        <select id="keepRecent" class="form-control">
                            <option value="5">5 conversas</option>
                            <option value="10" selected>10 conversas</option>
                            <option value="20">20 conversas</option>
                            <option value="50">50 conversas</option>
                        </select>
                    </div>
                    
                    <div class="warning-box">
                        <i class="bi bi-exclamation-triangle"></i>
                        <p>Esta ação não pode ser desfeita. As conversas excluídas serão removidas permanentemente.</p>
                    </div>
                </div>
            `,
            actions: [
                {
                    text: 'Cancelar',
                    class: 'btn-secondary',
                    action: () => this.closeModal()
                },
                {
                    text: 'Executar Limpeza',
                    class: 'btn-warning',
                    action: () => this.executeCleanup()
                }
            ]
        });
    }

    async executeCleanup() {
        try {
            const daysOld = parseInt(document.getElementById('daysOld').value);
            const keepRecent = parseInt(document.getElementById('keepRecent').value);
            
            this.closeModal();
            this.showNotification('Executando limpeza...', 'info');

            const response = await fetch('/api/chat/sessions/cleanup', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    days_old: daysOld,
                    keep_recent: keepRecent
                })
            });

            const data = await response.json();

            if (data.success) {
                this.showNotification(`${data.deleted_count} conversas antigas foram excluídas`, 'success');
                await this.loadSessions(); // Recarregar lista
            } else {
                this.showNotification(data.error || 'Erro na limpeza', 'error');
            }
        } catch (error) {
            console.error('Erro na limpeza:', error);
            this.showNotification('Erro na limpeza automática', 'error');
        }
    }

    showSelectDeleteModal() {
        const modal = this.createModal({
            title: 'Selecionar Conversas para Excluir',
            content: `
                <div class="select-delete-content">
                    <div class="select-actions">
                        <button class="btn btn-sm btn-outline-primary" onclick="chatManager.selectAllSessions()">
                            Selecionar Todas
                        </button>
                        <button class="btn btn-sm btn-outline-secondary" onclick="chatManager.deselectAllSessions()">
                            Desmarcar Todas
                        </button>
                    </div>
                    
                    <div class="sessions-list" id="selectableSessionsList">
                        ${this.renderSelectableSessions()}
                    </div>
                    
                    <div class="selected-count">
                        <span id="selectedCount">0</span> conversas selecionadas
                    </div>
                </div>
            `,
            actions: [
                {
                    text: 'Cancelar',
                    class: 'btn-secondary',
                    action: () => this.closeModal()
                },
                {
                    text: 'Excluir Selecionadas',
                    class: 'btn-danger',
                    action: () => this.deleteSelectedSessions()
                }
            ]
        });
    }

    renderSelectableSessions() {
        return this.sessions.map(session => {
            const timeAgo = this.getTimeAgo(new Date(session.last_activity));
            return `
                <div class="selectable-session">
                    <label class="session-checkbox">
                        <input type="checkbox" value="${session.id}" onchange="chatManager.updateSelectedCount()">
                        <div class="session-info">
                            <div class="session-title">${this.escapeHtml(session.title)}</div>
                            <div class="session-meta">
                                <span class="session-time">${timeAgo}</span>
                                <span class="session-messages">${session.message_count || 0} mensagens</span>
                            </div>
                        </div>
                    </label>
                </div>
            `;
        }).join('');
    }

    selectAllSessions() {
        const checkboxes = document.querySelectorAll('#selectableSessionsList input[type="checkbox"]');
        checkboxes.forEach(cb => cb.checked = true);
        this.updateSelectedCount();
    }

    deselectAllSessions() {
        const checkboxes = document.querySelectorAll('#selectableSessionsList input[type="checkbox"]');
        checkboxes.forEach(cb => cb.checked = false);
        this.updateSelectedCount();
    }

    updateSelectedCount() {
        const checkboxes = document.querySelectorAll('#selectableSessionsList input[type="checkbox"]:checked');
        const countElement = document.getElementById('selectedCount');
        if (countElement) {
            countElement.textContent = checkboxes.length;
        }
    }

    async deleteSelectedSessions() {
        try {
            const checkboxes = document.querySelectorAll('#selectableSessionsList input[type="checkbox"]:checked');
            const sessionIds = Array.from(checkboxes).map(cb => parseInt(cb.value));
            
            if (sessionIds.length === 0) {
                this.showNotification('Nenhuma conversa selecionada', 'warning');
                return;
            }

            this.closeModal();
            this.showNotification(`Excluindo ${sessionIds.length} conversas...`, 'info');

            const response = await fetch('/api/chat/sessions/bulk-delete', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    session_ids: sessionIds
                })
            });

            const data = await response.json();

            if (data.success) {
                // Remover da lista local
                this.sessions = this.sessions.filter(s => !sessionIds.includes(s.id));
                
                // Se a sessão atual foi excluída, limpar
                if (sessionIds.includes(this.currentSessionId)) {
                    this.currentSessionId = null;
                    this.chatMessages.innerHTML = '';
                    this.showWelcomeMessage();
                }
                
                this.renderSessions();
                this.showNotification(`${data.deleted_count} conversas excluídas com sucesso`, 'success');
            } else {
                this.showNotification(data.error || 'Erro ao excluir conversas', 'error');
            }
        } catch (error) {
            console.error('Erro ao excluir sessões:', error);
            this.showNotification('Erro ao excluir conversas', 'error');
        }
    }

    async getSessionStats() {
        try {
            const response = await fetch('/api/chat/sessions/stats');
            const data = await response.json();
            
            if (data.success) {
                return data.stats;
            }
        } catch (error) {
            console.error('Erro ao obter estatísticas:', error);
        }
        return null;
    }

    // Função auxiliar para criar modais
    createModal({ title, content, actions }) {
        // Remover modal existente
        this.closeModal();
        
        const modalHtml = `
            <div class="modal-overlay" id="chatModal">
                <div class="modal-content">
                    <div class="modal-header">
                        <h3>${title}</h3>
                        <button class="modal-close" onclick="chatManager.closeModal()">
                            <i class="bi bi-x"></i>
                        </button>
                    </div>
                    <div class="modal-body">
                        ${content}
                    </div>
                    <div class="modal-footer">
                        ${actions.map(action => 
                            `<button class="btn ${action.class}" onclick="${action.action.toString().replace('function ', '').replace('() => ', '').replace('()', '')}">${action.text}</button>`
                        ).join('')}
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        // Adicionar event listener para fechar ao clicar fora
        const overlay = document.getElementById('chatModal');
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                this.closeModal();
            }
        });
        
        return overlay;
    }

    closeModal() {
        const modal = document.getElementById('chatModal');
        if (modal) {
            modal.remove();
        }
    }

    showWelcomeMessage() {
        this.chatMessages.innerHTML = `
            <div class="welcome-message fade-in">
                <div class="welcome-content">
                    <div class="welcome-icon">
                        <i class="bi bi-robot"></i>
                    </div>
                    <h3 class="welcome-title">Bem-vindo ao Open Monitor AI</h3>
                    <p class="welcome-subtitle">Como posso ajudá-lo hoje? Você pode fazer perguntas sobre monitoramento, analise de dados ou qualquer outro topico.</p>
                    
                    <div class="quick-actions">
                        <button class="quick-action-btn" data-message="Como funciona o monitoramento?" aria-label="Enviar ação rápida: Como funciona?">
                            <i class="bi bi-question-circle"></i>
                            Como funciona?
                        </button>
                        <button class="quick-action-btn" data-message="Mostrar estatísticas do sistema" aria-label="Enviar ação rápida: Estatísticas">
                            <i class="bi bi-graph-up"></i>
                            Estatísticas
                        </button>
                        <button class="quick-action-btn" data-message="Configurar alertas" aria-label="Enviar ação rápida: Alertas">
                            <i class="bi bi-bell"></i>
                            Alertas
                        </button>
                    </div>
                </div>
            </div>
        `;
    }

    // Função para controlar o dropdown de ações da sessão
    toggleSessionDropdown(sessionId) {
        // Fechar todos os outros dropdowns
        document.querySelectorAll('.session-dropdown-menu').forEach(menu => {
            if (menu.id !== `dropdown-${sessionId}`) {
                menu.classList.remove('show');
            }
        });

        // Toggle do dropdown atual
        const dropdown = document.getElementById(`dropdown-${sessionId}`);
        if (dropdown) {
            dropdown.classList.toggle('show');
        }
    }

    // Função para arquivar sessão
    async archiveSession(sessionId) {
        try {
            const response = await fetch(`/api/chat/sessions/${sessionId}/archive`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const result = await response.json();
            
            if (result.success) {
                this.showNotification('Sessão arquivada com sucesso!', 'success');
                await this.loadSessions(); // Recarregar lista de sessões
                
                // Se a sessão arquivada era a atual, limpar o chat
                if (this.currentSessionId === sessionId) {
                    this.currentSessionId = null;
                    this.showWelcomeMessage();
                }
            } else {
                this.showNotification('Erro ao arquivar sessão: ' + result.error, 'error');
            }
        } catch (error) {
            console.error('Erro ao arquivar sessão:', error);
            this.showNotification('Erro ao arquivar sessão', 'error');
        }
    }

    // Função para mostrar notificações
    showNotification(message, type = 'info') {
        if (window.safeNotify) {
            window.safeNotify(type, null, message, 3000);
            return;
        }
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <div class="notification-content">
                <i class="bi bi-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
                <span>${message}</span>
            </div>
        `;
        document.body.appendChild(notification);
        setTimeout(() => notification.classList.add('show'), 100);
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }
}

// Initialize chat manager when DOM is loaded
let chatManager;
document.addEventListener('DOMContentLoaded', () => {
    chatManager = new ChatManager();
    
    // Fechar dropdowns ao clicar fora
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.session-dropdown')) {
            document.querySelectorAll('.session-dropdown-menu').forEach(menu => {
                menu.classList.remove('show');
            });
        }
    });
});