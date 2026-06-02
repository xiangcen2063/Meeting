import { useState, useRef, useCallback } from 'react';

export type RecordingStatus = 'idle' | 'recording' | 'stopped';

export function useAudioRecorder() {
  const [status, setStatus] = useState<RecordingStatus>('idle');
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [duration, setDuration] = useState(0);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);
  const startTimeRef = useRef<number>(0);

  const startRecording = useCallback(async () => {
    try {
      setError(null);
      setAudioBlob(null);
      chunksRef.current = [];

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus'
      });

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
        setAudioBlob(blob);
        stream.getTracks().forEach(track => track.stop());
        if (timerRef.current) {
          cancelAnimationFrame(timerRef.current);
        }
      };

      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start(100);
      setStatus('recording');
      startTimeRef.current = Date.now();

      const updateDuration = () => {
        setDuration(Math.floor((Date.now() - startTimeRef.current) / 1000));
        timerRef.current = requestAnimationFrame(updateDuration);
      };
      updateDuration();

    } catch (err) {
      setError('无法访问麦克风，请确保已授予权限');
      console.error('Error accessing microphone:', err);
    }
  }, []);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && status === 'recording') {
      mediaRecorderRef.current.stop();
      setStatus('stopped');
    }
  }, [status]);

  const reset = useCallback(() => {
    setStatus('idle');
    setAudioBlob(null);
    setDuration(0);
    setError(null);
  }, []);

  return {
    status,
    audioBlob,
    error,
    duration,
    startRecording,
    stopRecording,
    reset,
  };
}
