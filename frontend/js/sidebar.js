/**
 * Sidebar Controller
 * Handles sidebar toggle, collapse for mobile/tablet, backdrop overlay,
 * and conversation list management.
 */

class SidebarController {
  constructor() {
    this.sidebar = document.querySelector('.sidebar');
    this.toggleBtn = document.querySelector('.topbar-toggle');
    this.overlay = this._createOverlay();
    this.isOpen = false;
    this.isMobileView = window.innerWidth <= 1024;
    this.conversations = []; // [{ id, label, sessionId }]

    this._init();
  }

  _createOverlay() {
    const overlay = document.createElement('div');
    overlay.className = 'sidebar-overlay';
    document.body.appendChild(overlay);
    return overlay;
  }

  _init() {
    this.overlay.addEventListener('click', () => this.close());

    document.querySelectorAll('.sidebar-action').forEach(action => {
      action.addEventListener('click', () => {
        if (this.isMobileView) this.close();
      });
    });

    window.addEventListener('resize', () => this._handleResize());

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.isOpen) this.close();
    });

    this._updateViewState();
  }

  _handleResize() {
    const wasMobileView = this.isMobileView;
    this.isMobileView = window.innerWidth <= 1024;

    if (wasMobileView && !this.isMobileView) {
      this.sidebar.classList.remove('open');
      this.open();
    } else if (!wasMobileView && this.isMobileView) {
      this.sidebar.classList.remove('collapsed');
      this.close();
    }
  }

  _updateViewState() {
    this.isMobileView ? this.close() : this.open();
  }

  toggle() {
    this.isOpen ? this.close() : this.open();
  }

  open() {
    this.isOpen = true;
    this.sidebar.classList.add('open');
    this.sidebar.classList.remove('collapsed');

    if (this.isMobileView) {
      this.overlay.classList.add('visible');
      document.body.style.overflow = 'hidden';
    }
  }

  close() {
    this.isOpen = false;
    this.overlay.classList.remove('visible');
    document.body.style.overflow = '';

    if (this.isMobileView) {
      this.sidebar.classList.remove('open');
    } else {
      this.sidebar.classList.remove('open');
      this.sidebar.classList.add('collapsed');
    }
  }

  // Called from chat.js on the first message of a new session.
  // sessionId links this sidebar entry to the in-memory conversation store.
  addConversation(question, sessionId) {
    const label = question.length > 36 ? question.slice(0, 36) + '…' : question;
    const id = Date.now();
    this.conversations.unshift({ id, label, sessionId });

    const list = document.getElementById('conversation-list');
    const emptyEl = list.querySelector('.empty-convos');
    if (emptyEl) emptyEl.remove();

    list.querySelectorAll('.convo-item').forEach(el => el.classList.remove('active'));

    const btn = document.createElement('button');
    btn.className = 'convo-item active';
    btn.textContent = label;
    btn.title = question;

    btn.addEventListener('click', () => {
      // Mark as active in sidebar
      list.querySelectorAll('.convo-item').forEach(el => el.classList.remove('active'));
      btn.classList.add('active');

      // Restore the conversation messages in the chat panel
      Chat.restore(sessionId);

      if (this.isMobileView) this.close();
    });

    list.prepend(btn);
  }

  // Update the label of the most recent conversation item.
  // Useful if you want to rename a "New Chat" placeholder once
  // the first question is asked (future enhancement).
  updateLatestLabel(question) {
    const list = document.getElementById('conversation-list');
    const first = list.querySelector('.convo-item');
    if (!first) return;
    const label = question.length > 36 ? question.slice(0, 36) + '…' : question;
    first.textContent = label;
    first.title = question;
  }

  getState() {
    return {
      isOpen: this.isOpen,
      isMobileView: this.isMobileView,
      conversations: this.conversations,
      sidebarElement: this.sidebar,
      overlayElement: this.overlay
    };
  }
}

document.addEventListener('DOMContentLoaded', () => {
  window.sidebarController = new SidebarController();
});