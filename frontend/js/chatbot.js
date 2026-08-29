// Injects a floating chatbot widget into whatever page includes this script.
(function () {
  const toggle = document.createElement("button");
  toggle.id = "chat-toggle";
  toggle.title = "Ask the satellite assistant";
  toggle.textContent = "🛰️";

  const win = document.createElement("div");
  win.id = "chat-window";
  win.innerHTML = `
    <div id="chat-header">Mission Assistant (RAG)</div>
    <div id="chat-messages"></div>
    <div id="chat-input-row">
      <input id="chat-input" type="text" placeholder="Ask about a satellite or parameter..." />
      <button id="chat-send">Send</button>
    </div>
  `;

  document.body.appendChild(toggle);
  document.body.appendChild(win);

  const messagesEl = win.querySelector("#chat-messages");
  const inputEl = win.querySelector("#chat-input");
  const sendBtn = win.querySelector("#chat-send");

  function addMessage(text, who) {
    const div = document.createElement("div");
    div.className = `chat-msg ${who}`;
    div.textContent = text;
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  addMessage(
    "Hi! I'm the mission assistant. Ask me things like:\n" +
      '"what does attitude error mean?" or "how is Comsat-Delta doing?"',
    "bot"
  );

  toggle.addEventListener("click", () => win.classList.toggle("open"));

  async function send() {
    const text = inputEl.value.trim();
    if (!text) return;
    addMessage(text, "user");
    inputEl.value = "";
    try {
      const result = await apiPost("/chat", { message: text });
      addMessage(result.answer, "bot");
    } catch (e) {
      addMessage("Sorry, I couldn't reach the backend. Is the FastAPI server running?", "bot");
    }
  }

  sendBtn.addEventListener("click", send);
  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter") send();
  });
})();
