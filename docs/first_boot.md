# ⚙️ Initial Setup & First-Boot

[← Back to Overview](README.md)

On the very first launch of **aimo** (when no SQLite database or user accounts exist), the system automatically directs you to the **First-Boot Setup Wizard**.

---

## 🧙‍♂️ The First-Boot Wizard (`/setup`)

Before the system is made accessible for regular users, exactly one initial administrator must be created and the connection to your local AI server configured.

### 1. Initial Administrator (Super User)
- **Username:** Your desired display name.
- **Email Address:** Used alongside the password for subsequent logins.
- **Password:** A strong password (securely hashed via `bcrypt`).
- **Special Protection:** This first user automatically receives all functional permissions available across the system. These permissions are permanently protected and cannot be revoked or disabled.

### 2. Service Connections
- **Ollama URL (Mandatory):**  
  The network address of your Ollama server (default: `http://localhost:11434`). Ollama is strictly required for text generation, roleplay dialogue, and Vision image analysis.
- **SearXNG URL (Optional):**  
  Address for web search via tool-calling (currently disabled / TODO).
- **ComfyUI URL (Optional):**  
  The address of your ComfyUI server (default: `http://localhost:8188`) for generative image workflows in chat. Can also be configured later in the [Admin Panel](admin.md).

---

## 🔒 Post-Setup: Closed System

Once the setup wizard is successfully completed:
1. **Permanent Lockout:** The `/setup` route is immediately rendered inaccessible.
2. **No Public Registration:** There is no self-registration endpoint. New accounts can only be provisioned by an administrator through the [Admin Panel](admin.md).
3. **Regular Login:** All users authenticate via the login portal (`/login`) using email and password.

Continue to: [**The Hub Dashboard →**](hub.md)
