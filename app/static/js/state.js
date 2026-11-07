/**
 * Nagarkot Access Control Service - Global State Management
 * Maintains acting user context, user directory, and state change subscribers.
 */

const STORAGE_KEY = "nagarkot_acting_user";

class AppState {
  constructor() {
    this.users = [];
    this.currentUser = localStorage.getItem(STORAGE_KEY) || "asha-rao";
    this.currentUserObj = null;
    this.listeners = {
      userChange: [],
    };
  }

  setUsers(usersList) {
    this.users = usersList || [];
    // If stored user doesn't exist in directory, default to asha-rao or first user
    const found = this.users.find(u => u.id === this.currentUser);
    if (!found && this.users.length > 0) {
      const defaultUser = this.users.find(u => u.id === "asha-rao") || this.users[0];
      this.setUser(defaultUser.id, false);
    } else if (found) {
      this.currentUserObj = found;
    }
  }

  getUser(userId) {
    return this.users.find(u => u.id === userId) || null;
  }

  setUser(userId, notify = true) {
    this.currentUser = userId;
    this.currentUserObj = this.users.find(u => u.id === userId) || null;
    localStorage.setItem(STORAGE_KEY, userId);

    if (notify) {
      this.listeners.userChange.forEach(fn => {
        try {
          fn(this.currentUser, this.currentUserObj);
        } catch (err) {
          console.error("Error in userChange listener:", err);
        }
      });
    }
  }

  onUserChange(fn) {
    this.listeners.userChange.push(fn);
  }
}

export const state = new AppState();
