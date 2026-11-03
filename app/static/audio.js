/* A recording, a genuinely Maltese voice, or an explicit guide. No surrogate TTS. */
export function malteseVoice(voices) {
  return voices.find(v => /^(?:mt(?:-MT)?|mlt)(?:-|$)/i.test(v.lang.replace(/_/g,'-'))) || null;
}
export async function availableVoice(synth) {
  if (!synth) return null;
  const immediate = malteseVoice(synth.getVoices());
  if (immediate) return immediate;
  return new Promise(resolve => {
    const changed = () => { const voice = malteseVoice(synth.getVoices()); if (voice) finish(voice); };
    const timer = setTimeout(() => finish(malteseVoice(synth.getVoices())), 600);
    function finish(voice) { clearTimeout(timer); synth.removeEventListener('voiceschanged',changed); resolve(voice); }
    synth.addEventListener('voiceschanged',changed);
  });
}
export function createPronouncer({synth = globalThis.speechSynthesis,
  AudioClass = globalThis.Audio, Utterance = globalThis.SpeechSynthesisUtterance,
  guide, status}) {
  let playing, sequence = 0;
  function stop() { sequence++; if (playing) { playing.pause(); playing = null; } synth?.cancel(); }
  async function play(text, audioUrl = null) {
    stop();
    const ticket = sequence;
    if (audioUrl) {
      let fallbackStarted = false;
      const fallback = () => {
        if (ticket !== sequence || fallbackStarted) return;
        fallbackStarted = true;
        if (playing) { playing.pause(); playing = null; }
        return useVoice(text, ticket);
      };
      try {
        playing = new AudioClass(audioUrl);
        const native = playing;
        native.addEventListener('error', fallback, {once:true});
        await native.play();
        if (ticket === sequence && !fallbackStarted) status('Wikimedia 真人录音 / native recording');
        return;
      } catch { await fallback(); return; }
    }
    await useVoice(text, ticket);
  }
  async function useVoice(text, ticket) {
    const voice = await availableVoice(synth);
    if (ticket !== sequence) return;
    if (!voice || !Utterance) { guide(text); return; }
    const utterance = new Utterance(text);
    utterance.voice = voice;
    utterance.lang = 'mt-MT';
    utterance.rate = .85;
    utterance.onerror = event => { if (ticket === sequence && !['canceled','interrupted'].includes(event.error)) guide(text); };
    status(`马耳他语合成 / Maltese TTS · ${voice.name}`);
    synth.speak(utterance);
  }
  return {play, stop};
}
