import { useEffect, useState } from 'react';
import { useAudioRecorder } from '../hooks/useAudioRecorder';
import './VoiceRecorder.css';

interface VoiceRecorderProps {
  onRecordingComplete: (blob: Blob) => void;
  onTextSubmit: (text: string) => void;
  disabled?: boolean;
}

export function VoiceRecorder({ onRecordingComplete, onTextSubmit, disabled }: VoiceRecorderProps) {
  const [inputMode, setInputMode] = useState<'text' | 'voice'>('text');
  const [textInput, setTextInput] = useState('');
  const {
    status,
    audioBlob,
    error,
    duration,
    startRecording,
    stopRecording,
    reset,
  } = useAudioRecorder();

  useEffect(() => {
    if (error) {
      setInputMode('text');
    }
  }, [error]);

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const handleSend = () => {
    if (audioBlob) {
      onRecordingComplete(audioBlob);
      reset();
    }
  };

  const handleTextSubmit = () => {
    const value = textInput.trim();
    if (!value) {
      return;
    }

    onTextSubmit(value);
  };

  return (
    <section className="voice-recorder" aria-label="位置输入">
      <div className="panel-heading">
        <div>
          <span className="panel-step">第 1 步</span>
          <h2>告诉我双方在哪里</h2>
        </div>
        <p>建议写清城市、你的位置、朋友的位置。</p>
      </div>

      <div className="mode-switch" role="tablist" aria-label="输入方式">
        <button
          type="button"
          className={inputMode === 'text' ? 'active' : ''}
          onClick={() => setInputMode('text')}
          disabled={disabled}
          role="tab"
          aria-selected={inputMode === 'text'}
        >
          文字输入
        </button>
        <button
          type="button"
          className={inputMode === 'voice' ? 'active' : ''}
          onClick={() => setInputMode('voice')}
          disabled={disabled}
          role="tab"
          aria-selected={inputMode === 'voice'}
        >
          录音输入
        </button>
      </div>

      {inputMode === 'text' && (
        <div className="text-entry">
          {error && (
            <div className="mic-notice" role="status">
              当前无法访问麦克风，已为你切换到文字输入
            </div>
          )}

          <label htmlFor="locationText">位置描述</label>
          <textarea
            id="locationText"
            value={textInput}
            onChange={(event) => setTextInput(event.target.value)}
            placeholder="例如：我在南京南站，朋友在新街口，城市是南京"
            rows={5}
            disabled={disabled}
          />
          <button
            className="text-submit-btn"
            onClick={handleTextSubmit}
            disabled={disabled || !textInput.trim()}
          >
            查询会面地点
          </button>
        </div>
      )}

      {inputMode === 'voice' && (
        <div className="voice-entry">
          <div className="recorder-controls">
            {status === 'idle' && (
              <button
                className="record-btn"
                onClick={startRecording}
                disabled={disabled}
              >
                <span className="mic-icon" aria-hidden="true"></span>
                <span>开始录音</span>
              </button>
            )}

            {status === 'recording' && (
              <div className="recording-state">
                <div className="recording-indicator">
                  <span className="pulse"></span>
                  <span className="duration">{formatDuration(duration)}</span>
                </div>
                <button className="stop-btn" onClick={stopRecording}>
                  <span className="stop-icon" aria-hidden="true"></span>
                  <span>停止录音</span>
                </button>
              </div>
            )}

            {status === 'stopped' && audioBlob && (
              <div className="preview-state">
                <audio controls src={URL.createObjectURL(audioBlob)} />
                <div className="preview-actions">
                  <button className="retry-btn" onClick={reset} disabled={disabled}>
                    重录
                  </button>
                  <button className="send-btn" onClick={handleSend} disabled={disabled}>
                    发送录音
                  </button>
                </div>
              </div>
            )}
          </div>

          <p className="hint">
            {status === 'idle' && '点击开始录音后，说出双方位置和城市。'}
            {status === 'recording' && '正在录音，请描述你和朋友的当前位置。'}
            {status === 'stopped' && '录音完成，可以预览、重录或发送。'}
          </p>
        </div>
      )}
    </section>
  );
}
