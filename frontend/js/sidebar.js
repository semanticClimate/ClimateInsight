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
    this.conversations = []; // [{ id, label }]

    this._init();
  }

  _createOverlay() {
    const overlay = document.createElement('div');
    overlay.className = 'sidebar-overlay';
    document.body.appendChild(overlay);
    return overlay;
  }

  _init() {
    // Note: the toggle button click is wired in main.js via window.sidebarController.toggle()

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
      // Switching to desktop: clear mobile transform state
      this.sidebar.classList.remove('open');
      this.open();
    } else if (!wasMobileView && this.isMobileView) {
      // Switching to mobile: clear desktop collapsed state
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
      // Mobile uses transform — just remove 'open', don't touch 'collapsed'
      this.sidebar.classList.remove('open');
    } else {
      // Desktop uses width — 'collapsed' collapses the sidebar
      this.sidebar.classList.remove('open');
      this.sidebar.classList.add('collapsed');
    }
  }

  addConversation(question) {
    const label = question.length > 36 ? question.slice(0, 36) + '…' : question;
    const id = Date.now();
    this.conversations.unshift({ id, label });

    const list = document.getElementById('conversation-list');
    const emptyEl = list.querySelector('.empty-convos');
    if (emptyEl) emptyEl.remove();

    list.querySelectorAll('.convo-item').forEach(el => el.classList.remove('active'));

    const btn = document.createElement('button');
    btn.className = 'convo-item active';
    btn.textContent = label;
    btn.title = question;
    btn.addEventListener('click', () => {
      list.querySelectorAll('.convo-item').forEach(el => el.classList.remove('active'));
      btn.classList.add('active');
      if (this.isMobileView) this.close();
    });

    list.prepend(btn);
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