# 📞 IVR Integration Layer Simulator

This project serves as a comprehensive simulator for **Integration Layer Development**. Its objective is to demonstrate a middleware (API layer) that connects a legacy Interactive Voice Response (IVR) system's VXML logic to a modern Conversational AI stack (simulated by the FastAPI backend).

The simulator is split into a Python backend (the API/middleware) and a browser-based frontend (the IVR client/phone simulator).

---

## 🚀 Project Components

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Backend API (Middleware)** | **Python / FastAPI** | Simulates the core IVR business logic (menus, actions, call state) and exposes REST endpoints (`/ivr/start`, `/ivr/dtmf`) that the client calls. This acts as the translation layer between the legacy IVR and the AI stack. |
| **Frontend Client** | **HTML / JavaScript** | A visual phone simulator that initiates calls and sends DTMF inputs. It consumes the FastAPI API, and uses the browser's Web Speech API for audible voice prompts. |

---

## 🛠️ Setup and Installation

Follow these steps to get the system running locally:

### 1. Clone the Repository (If starting fresh, skip to 2)


```Bash

git clone https://github.com/YOUR_GITHUB_USERNAME/REPOSITORY_NAME.gitcd REPOSITORY_NAME

```


### 2. Install Python Dependencies

This project requires Python 3.7+ and the following libraries:


```Bash

# Install FastAPI, Uvicorn (ASGI server), and Pydantic
pip install fastapi uvicorn pydantic

```


### 3. Start the Backend API (Integration Layer)

Start the Python server. This will run the API on `http://localhost:8000`.


```Bash

python -m uvicorn ivr_simulator_backend:app --reload

```

**Note:** Keep this terminal window open while testing the application.

---

## ▶️ How to Run the Simulator

1.Ensure the **Backend API** is running in your terminal window (as described above).

2.Open the `ivr_simulator.html` file directly in a modern web browser (e.g., Chrome, Firefox, Edge) by double-clicking the file.

### Testing the Flow

1.Click the 📞 **Start Call** button on the simulator.

2.The browser should begin speaking the main menu prompt (e.g., "Welcome to Air India Airlines...").

3.Press the **keypad buttons (1, 2, 9)** to navigate the IVR menu structure defined in `ivr_simulator_backend.py`.

4.Observe the API calls and responses logged in the **Python terminal** and the updates on the **simulator screen**.

---

## ✅ Deliverables Met

This simulator successfully addresses the core objectives of the Integration Layer Development module:

* **Design and implement connectors or APIs to enable communication between VXML and ACS/BAP:** The `/ivr/start` and `/ivr/dtmf` API endpoints fulfill this requirement by providing a standardized interface for IVR input/output.

* **Ensure real-time data handling and system compatibility:** The FastAPI application handles real-time state management (storing `call_id`, `current_menu`, etc.) for each active session.

* **Validate integration layer with sample transaction and flow testing:** The HTML client enables interactive end-to-end testing of the defined IVR paths (e.g., booking enquiry, flight status lookup).

---

## 📝 License

This project is licensed under the MIT License. (You can change this if needed)
