// Stands in for @google/genai's Live API when tests/js/callpage.mjs bundles the call page. Each connect follows the next
// step in globalThis.__live.steps:
//   {close: [code, reason]}   the socket closes before the session is set up (how a 503 arrives); like the SDK,
//                              connect then never resolves
//   {ok: true, say, dropAfter} set up; `say` sends some of a model turn first, `dropAfter` (ms) closes it with 1011
//   {ok: true, tools}          set up, then one toolCall message with these functionCalls
//   {ok: true, messages}       set up, then these server messages in order ({wait: ms} pauses between them)
export class GoogleGenAI {
  constructor(opts) {
    this.opts = opts;
    this.live = { connect: (p) => connect(p) };
  }
}

function connect({ model, config, callbacks }) {
  const L = globalThis.__live;
  const step = L.steps.length ? L.steps.shift() : { ok: true };
  L.connects.push({ model, config });
  return new Promise((resolve) => {
    setTimeout(() => {
      if (callbacks.onopen) callbacks.onopen();
      if (step.close) { callbacks.onclose({ code: step.close[0], reason: step.close[1] }); return; }
      const session = {
        sent: [],
        closed: false,
        sendClientContent(x) { this.sent.push(x); },
        sendRealtimeInput() {},
        sendToolResponse(x) { this.sent.push(x); },
        close() { if (!this.closed) { this.closed = true; setTimeout(() => callbacks.onclose({ code: 1000, reason: '' }), 0); } },
      };
      L.sessions.push(session);
      resolve(session);
      setTimeout(() => {
        if (step.say) callbacks.onmessage({ serverContent: { outputTranscription: { text: step.say }, turnComplete: true } });
        if (step.tools) callbacks.onmessage({ toolCall: { functionCalls: step.tools } });
        if (step.messages) (async () => { for (const m of step.messages) { if (m.wait) await new Promise((r) => setTimeout(r, m.wait)); else if (!session.closed) callbacks.onmessage(m); } })();
        if (step.dropAfter) setTimeout(() => { if (!session.closed) { session.closed = true; callbacks.onclose({ code: 1011, reason: 'The service is currently unavailable.' }); } }, step.dropAfter);
      }, 5);
    }, 5);
  });
}
