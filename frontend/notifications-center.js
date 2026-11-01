/**
 * Stage 4: In-App Notification Center for AccessReaper v2
 * Manages notification bell badge, dropdown list, mark read actions, and navigation.
 */

const NotificationsCenter = {
  unreadCount: 0,
  notifications: [],
  isOpen: false,
  pollTimer: null,
  seenIds: new Set(),
  isFirstFetch: true,

  async init() {
    this.bindEvents();
    await this.fetchNotifications();
    if (!this.pollTimer) {
      this.pollTimer = setInterval(() => this.fetchNotifications(), 3500);
    }
  },

  bindEvents() {
    const bellBtn = document.getElementById("notification-bell");
    if (bellBtn) {
      bellBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        this.toggle();
      });
    }

    const markAllBtn = document.getElementById("mark-all-notifications-read");
    if (markAllBtn) {
      markAllBtn.addEventListener("click", async (e) => {
        e.stopPropagation();
        await this.markAllRead();
      });
    }

    document.addEventListener("click", (e) => {
      const panel = document.getElementById("notification-panel");
      const bell = document.getElementById("notification-bell");
      if (this.isOpen && panel && !panel.contains(e.target) && !bell.contains(e.target)) {
        this.close();
      }
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this.isOpen) {
        this.close();
      }
    });
  },

  toggle() {
    if (this.isOpen) {
      this.close();
    } else {
      this.open();
    }
  },

  open() {
    const panel = document.getElementById("notification-panel");
    const bell = document.getElementById("notification-bell");
    if (panel) {
      panel.classList.remove("d-none");
      this.isOpen = true;
      if (bell) bell.setAttribute("aria-expanded", "true");
      this.render();
    }
  },

  close() {
    const panel = document.getElementById("notification-panel");
    const bell = document.getElementById("notification-bell");
    if (panel) {
      panel.classList.add("d-none");
      this.isOpen = false;
      if (bell) bell.setAttribute("aria-expanded", "false");
    }
  },

  async fetchNotifications() {
    if (!window.ApiClient || window.ApiClient.isDemoMode) {
      this.unreadCount = 0;
      this.notifications = [];
      this.updateBadge();
      return;
    }

    try {
      const res = await ApiClient.getNotifications();
      const freshList = res.notifications || [];
      const newUnreadCount = res.unreadCount || 0;

      if (this.isFirstFetch) {
        freshList.forEach((n) => this.seenIds.add(n.id));
        this.isFirstFetch = false;
        this.unreadCount = newUnreadCount;
        this.notifications = freshList;
        this.updateBadge();
        return;
      }

      // Check for freshly arrived notifications
      const newlyArrived = [];
      let shouldAutoRefreshView = false;

      for (const n of freshList) {
        if (!this.seenIds.has(n.id)) {
          this.seenIds.add(n.id);
          newlyArrived.push(n);
          if (["audit_completed", "high_findings", "jit_expired", "access_requested", "direct_access_detected", "approval_decided"].includes(n.eventType)) {
            shouldAutoRefreshView = true;
          }
        }
      }

      this.unreadCount = newUnreadCount;
      this.notifications = freshList;
      this.updateBadge();

      // Instantly pop up toast for all newly arrived unread notifications
      for (const n of newlyArrived) {
        if (!n.isRead && typeof showToast === "function") {
          showToast(`🔔 ${n.title}: ${n.message}`);
        }
      }

      // Live update active views without pressing F5!
      if (shouldAutoRefreshView && window.ApiClient && !window.ApiClient.isDemoMode) {
        try {
          const freshBootstrap = await ApiClient.bootstrap();
          ApiClient.syncState(freshBootstrap);
          if (typeof render === "function") {
            render();
          }
        } catch (refreshErr) {
          console.warn("Background auto-refresh error:", refreshErr);
        }
      }

      if (this.isOpen) {
        this.render();
      }
    } catch (err) {
      console.warn("Failed to fetch notifications:", err);
    }
  },

  updateBadge() {
    const badge = document.getElementById("notification-unread-count");
    if (!badge) return;

    if (this.unreadCount > 0) {
      badge.textContent = this.unreadCount > 99 ? "99+" : this.unreadCount;
      badge.style.display = "inline-flex";
    } else {
      badge.style.display = "none";
    }
  },

  async markRead(id, link = null) {
    const notif = this.notifications.find((n) => n.id === id);
    if (notif && !notif.isRead) {
      notif.isRead = true;
      if (this.unreadCount > 0) this.unreadCount -= 1;
      this.updateBadge();
      if (window.ApiClient && !window.ApiClient.isDemoMode) {
        try {
          await ApiClient.markNotificationRead(id);
        } catch (err) {
          console.warn("Error marking notification read:", err);
        }
      }
    }

    this.close();
    if (link) {
      location.hash = link.startsWith("#") ? link : `#${link}`;
    }
  },

  async markAllRead() {
    this.notifications.forEach((n) => (n.isRead = true));
    this.unreadCount = 0;
    this.updateBadge();
    this.render();

    if (window.ApiClient && !window.ApiClient.isDemoMode) {
      try {
        await ApiClient.markAllNotificationsRead();
        if (typeof showToast === "function") {
          showToast("All notifications marked as read");
        }
      } catch (err) {
        console.warn("Error marking all read:", err);
      }
    }
  },

  formatTime(isoStr) {
    if (!isoStr) return "";
    try {
      const d = new Date(isoStr);
      const diffMs = Date.now() - d.getTime();
      const diffMins = Math.floor(diffMs / 60000);
      if (diffMins < 1) return "Just now";
      if (diffMins < 60) return `${diffMins}m ago`;
      const diffHours = Math.floor(diffMins / 60);
      if (diffHours < 24) return `${diffHours}h ago`;
      return d.toLocaleDateString([], { month: "short", day: "numeric" });
    } catch {
      return isoStr;
    }
  },

  getIconForEvent(type) {
    switch (type) {
      case "high_findings":
      case "direct_access_detected":
        return `<span class="notif-icon-badge danger" aria-hidden="true">!</span>`;
      case "sync_degraded":
      case "audit_paused":
        return `<span class="notif-icon-badge warning" aria-hidden="true">${uiIcon('alert', 12)}</span>`;
      case "jit_expired":
      case "approval_overdue":
        return `<span class="notif-icon-badge warning" aria-hidden="true">${uiIcon('clock', 12)}</span>`;
      case "access_requested":
      case "user_pending_activation":
        return `<span class="notif-icon-badge info" aria-hidden="true">${uiIcon('people', 12)}</span>`;
      case "approval_decided":
        return `<span class="notif-icon-badge success" aria-hidden="true">✓</span>`;
      default:
        return `<span class="notif-icon-badge default" aria-hidden="true">${uiIcon('bell', 12)}</span>`;
    }
  },

  render() {
    const listEl = document.getElementById("notification-list");
    if (!listEl) return;

    if (!this.notifications.length) {
      listEl.innerHTML = `
        <div class="notification-empty">
          <div style="font-size: 24px; margin-bottom: 6px; color: var(--muted, #94a3b8);">${uiIcon('bellOff', 26)}</div>
          <strong>No notifications</strong>
          <small style="color: var(--muted, #64748b);">You're all caught up on IAM audit and access events.</small>
        </div>
      `;
      return;
    }

    listEl.innerHTML = this.notifications
      .map((n) => {
        const unreadClass = n.isRead ? "" : " unread";
        const icon = this.getIconForEvent(n.eventType);
        const timeStr = this.formatTime(n.createdAt);
        return `
          <div class="notification-item${unreadClass}" data-notif-id="${n.id}" data-notif-link="${n.link || ''}">
            <div class="notif-icon-col">${icon}</div>
            <div class="notif-body-col">
              <div class="notif-title-row">
                <strong class="notif-title">${typeof safe === 'function' ? safe(n.title) : n.title}</strong>
                <span class="notif-time">${timeStr}</span>
              </div>
              <p class="notif-message">${typeof safe === 'function' ? safe(n.message) : n.message}</p>
            </div>
            ${!n.isRead ? '<span class="notif-unread-dot" aria-label="Unread"></span>' : ""}
          </div>
        `;
      })
      .join("");

    listEl.querySelectorAll(".notification-item").forEach((item) => {
      item.addEventListener("click", () => {
        const id = item.dataset.notifId;
        const link = item.dataset.notifLink;
        this.markRead(id, link);
      });
    });
  },
};

window.NotificationsCenter = NotificationsCenter;

// Initialize on DOM ready or immediately if loaded
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => NotificationsCenter.init());
} else {
  NotificationsCenter.init();
}
