import { useState } from 'react';
import { VoiceRecorder } from './components/VoiceRecorder';
import type { MeetingSlots } from './components/ResponseDisplay';
import { ResponseDisplay } from './components/ResponseDisplay';
import { sendTextForMeetingPoint, sendVoiceForMeetingPoint } from './api/meeting';
import './App.css';

function normalizeLocationText(value: string) {
  return value
    .replace(/[，。；;,.、\n\r]+$/g, '')
    .trim();
}

function parseSubmittedLocations(text: string): MeetingSlots | null {
  const location1Match = text.match(/(?:我|我的位置|你的位置|本人)(?:在|位于|是)([^，。；;,\n]+)/);
  const location2Match = text.match(/(?:朋友|我朋友|我的朋友|对方|同伴)(?:在|位于|是)([^，。；;,\n]+)/);

  const location1 = normalizeLocationText(location1Match?.[1] || '');
  const location2 = normalizeLocationText(location2Match?.[1] || '');

  if (!location1 && !location2) {
    return null;
  }

  return {
    location1,
    location2,
  };
}

function mergeSlots(primary?: MeetingSlots | null, fallback?: MeetingSlots | null): MeetingSlots | null {
  if (!primary && !fallback) {
    return null;
  }

  return {
    ...fallback,
    ...primary,
    location1: primary?.location1 || fallback?.location1 || '',
    location2: primary?.location2 || fallback?.location2 || '',
  };
}

function App() {
  const [isLoading, setIsLoading] = useState(false);
  const [textResponse, setTextResponse] = useState<string | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [slots, setSlots] = useState<MeetingSlots | null>(null);
  const hasResult = Boolean(textResponse || audioUrl);

  const handleRecordingComplete = async (audioBlob: Blob) => {
    setIsLoading(true);
    setError(null);
    setTextResponse(null);
    setAudioUrl(null);
    setSlots(null);

    try {
      const response = await sendVoiceForMeetingPoint(audioBlob);

      if (response.success) {
        setTextResponse(response.textResponse || null);
        setAudioUrl(response.audioUrl || null);
        setSlots(response.slots || null);
      } else {
        setError(response.error || '处理失败，请重试');
      }
    } catch (err) {
      console.error('Error sending voice:', err);
      setError('网络错误，请检查连接后重试');
    } finally {
      setIsLoading(false);
    }
  };

  const handleTextSubmit = async (text: string) => {
    const submittedSlots = parseSubmittedLocations(text);

    setIsLoading(true);
    setError(null);
    setTextResponse(null);
    setAudioUrl(null);
    setSlots(submittedSlots);

    try {
      const response = await sendTextForMeetingPoint(text);

      if (response.success) {
        setTextResponse(response.textResponse || null);
        setAudioUrl(response.audioUrl || null);
        setSlots(mergeSlots(response.slots, submittedSlots));
      } else {
        setError(response.error || '处理失败，请重试');
      }
    } catch (err) {
      console.error('Error sending text:', err);
      setError('网络错误，请检查连接后重试');
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setTextResponse(null);
    setAudioUrl(null);
    setError(null);
    setSlots(null);
  };

  return (
    <div className="app">
      <div className="app-container">
        <header className="app-header">
          <div className="app-title-row">
            <div>
              <span className="app-kicker">高德地图会面助手</span>
              <h1>会面地点推荐</h1>
            </div>
            <span className="app-status">{isLoading ? '分析中' : hasResult ? '已推荐' : '待输入'}</span>
          </div>
          <p>输入双方位置，系统会识别地点并给出适合会面的方案。</p>

          <ol className="flow-steps" aria-label="查询流程">
            <li className={!hasResult && !isLoading ? 'active' : ''}>输入位置</li>
            <li className={isLoading ? 'active' : ''}>分析路线</li>
            <li className={hasResult ? 'active' : ''}>查看推荐</li>
          </ol>
        </header>

        <main className="app-main">
          {!hasResult && !isLoading && (
            <VoiceRecorder
              onRecordingComplete={handleRecordingComplete}
              onTextSubmit={handleTextSubmit}
              disabled={isLoading}
            />
          )}

          <ResponseDisplay
            textResponse={textResponse}
            audioUrl={audioUrl}
            slots={slots}
            isLoading={isLoading}
            error={error}
          />

          {(hasResult || error) && !isLoading && (
            <button className="reset-btn" onClick={handleReset}>
              重新查询
            </button>
          )}
        </main>

        <footer className="app-footer">
          <p>基于高德地图服务 · 语音由阿里云提供</p>
        </footer>
      </div>
    </div>
  );
}

export default App;
