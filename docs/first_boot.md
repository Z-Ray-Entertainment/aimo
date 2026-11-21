# ⚙️ Initial Setup & First-Boot

[← Back to Overview](README.md)

On the very first launch of **AImo** (when no user accounts exist yet), the system automatically directs you to the **First-Boot Setup Wizard**.

---

## 🧙‍♂️ The First-Boot Wizard (`/setup`)

Before the system is made accessible for regular users, the initial administrator account and the exclusive AI backend are configured in three guided steps:

### 1. Initial Administrator (Super User)
- **Username:** Your desired display name.
- **Email Address:** Used alongside the password for subsequent logins.
- **Password:** A strong password.
- **Special Protection:** This first user automatically receives all functional permissions available across the system. These permissions are permanently protected and cannot be revoked or disabled.

### 2. Select AI Backend
Choose between **Ollama (Local / Self-Hosted)** and **Google AI Cloud (Gemini API)**. Only one AI backend is active at a time; you can switch your choice anytime later under **Admin → Services & Models**.

### 3. Configure Backend
Depending on your choice in Step 2, the wizard configures the selected backend:

- **If Ollama is selected:**
  - **Ollama Server URL:** The address of your Ollama server (default: `http://localhost:11434`) with a one-click connection test.
  - **Recommended Models per Role:**
    - **🎭 Roleplay:** `igorls/gemma-4-12B-it-qat-q4_0-unquantized-heretic:latest`
    - **🧠 Memory:** `igorls/gemma-4-12B-it-qat-q4_0-unquantized-heretic:latest`
    - **✨ Assistant:** `gemma4:e4b`
    - **👁️ Vision:** `gemma4:e4b`
    - **🏷️ Classification:** `llama3.2:1b`
  - **Integrated Model Manager:** After checking the Ollama connection, each role row displays whether its recommended model is **✔ Ready** or **⏳ Missing**. For any missing model, a **📥 Pull** button appears directly on that row to download and install the model inside the wizard with live progress feedback. Once installed, the Pull button automatically yields to the **✔ Ready** badge.
- **If Google AI Cloud is selected:**
  - Enter and verify your **Google AI API Key** and optionally customize the Gemini model assignment per role.

---

## 🔒 Post-Setup: Closed System

Once the setup wizard is successfully completed:
1. **Permanent Lockout:** The `/setup` route is immediately rendered inaccessible.
2. **No Public Registration:** There is no self-registration endpoint. New accounts can only be provisioned by an administrator through the [Admin Panel](admin.md).
3. **Regular Login:** All users authenticate via the login portal (`/login`) using email and password.

Continue to: [**The Hub Dashboard →**](hub.md)
