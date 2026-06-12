/** Record 16 kHz mono PCM WAV via hold-to-talk (browser). */

let mediaStream = null;
let audioContext = null;
let processor = null;
let sourceNode = null;
let silentGain = null;
let recordedChunks = [];

function _encodeWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);

  const writeString = (offset, str) => {
    for (let i = 0; i < str.length; i++) {
      view.setUint8(offset + i, str.charCodeAt(i));
    }
  };

  writeString(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeString(8, "WAVE");
  writeString(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(36, "data");
  view.setUint32(40, samples.length * 2, true);

  let offset = 44;
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    offset += 2;
  }

  return new Blob([buffer], { type: "audio/wav" });
}

function _downsample(buffer, inputRate, outputRate) {
  if (outputRate === inputRate) {
    return buffer;
  }
  const ratio = inputRate / outputRate;
  const newLength = Math.round(buffer.length / ratio);
  const result = new Float32Array(newLength);
  for (let i = 0; i < newLength; i++) {
    const idx = Math.floor(i * ratio);
    result[i] = buffer[idx];
  }
  return result;
}

function _peakAmplitude(samples) {
  let peak = 0;
  for (let i = 0; i < samples.length; i++) {
    const v = Math.abs(samples[i]);
    if (v > peak) peak = v;
  }
  return peak;
}

async function ensureMicAccess() {
  if (mediaStream) {
    return mediaStream;
  }
  mediaStream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
  });
  return mediaStream;
}

export async function startRecording() {
  const stream = await ensureMicAccess();
  audioContext = new AudioContext();
  if (audioContext.state === "suspended") {
    await audioContext.resume();
  }

  sourceNode = audioContext.createMediaStreamSource(stream);
  processor = audioContext.createScriptProcessor(4096, 1, 1);
  silentGain = audioContext.createGain();
  silentGain.gain.value = 0;
  recordedChunks = [];

  processor.onaudioprocess = (event) => {
    recordedChunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
  };

  sourceNode.connect(processor);
  processor.connect(silentGain);
  silentGain.connect(audioContext.destination);
}

export async function stopRecording() {
  if (processor) {
    processor.disconnect();
    processor.onaudioprocess = null;
    processor = null;
  }
  if (sourceNode) {
    sourceNode.disconnect();
    sourceNode = null;
  }
  if (silentGain) {
    silentGain.disconnect();
    silentGain = null;
  }

  const sampleRate = audioContext?.sampleRate || 48000;
  if (audioContext) {
    await audioContext.close();
    audioContext = null;
  }

  const totalLength = recordedChunks.reduce((sum, c) => sum + c.length, 0);
  const merged = new Float32Array(totalLength);
  let offset = 0;
  for (const chunk of recordedChunks) {
    merged.set(chunk, offset);
    offset += chunk.length;
  }
  recordedChunks = [];

  const pcm16k = _downsample(merged, sampleRate, 16000);
  const peak = _peakAmplitude(pcm16k);
  const blob = _encodeWav(pcm16k, 16000);
  return { blob, peak, durationSec: pcm16k.length / 16000 };
}

export function isRecordingSupported() {
  return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
}
