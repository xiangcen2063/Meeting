import { useRef, useEffect, useState } from 'react';
import './ResponseDisplay.css';

interface ResponseDisplayProps {
  textResponse: string | null;
  audioUrl: string | null;
  slots: MeetingSlots | null;
  isLoading: boolean;
  error: string | null;
}

export interface MeetingSlots {
  location1?: string;
  location2?: string;
  city?: string;
  location1Formatted?: string;
  location2Formatted?: string;
}

interface ParsedMeetingResponse {
  location1: string;
  location2: string;
  recommendation: string;
}

const analysisSteps = [
  {
    title: '识别位置',
    description: '正在提取你和朋友的位置',
  },
  {
    title: '计算路线',
    description: '正在估算双方距离和可达性',
  },
  {
    title: '生成推荐',
    description: '正在整理适合会面的方案',
  },
];

function cleanLine(line: string) {
  return line
    .replace(/^[\s🎯📍✨📊-]+/, '')
    .replace(/^(你的位置|我的位置|我位置|朋友位置|朋友的位置|对方位置|对方的位置|推荐方案|位置信息|会面地点推荐)[：:]\s*/, '$1: ')
    .trim();
}

function getValueAfterLabel(lines: string[], labels: string[]) {
  for (const line of lines) {
    for (const label of labels) {
      if (line.startsWith(`${label}:`)) {
        return line.replace(`${label}:`, '').trim();
      }
    }
  }

  return '';
}

function parseMeetingResponse(text: string): ParsedMeetingResponse {
  const lines = text
    .split('\n')
    .map(cleanLine)
    .filter(Boolean);

  const storageIndex = lines.findIndex(line =>
    line.includes('详细信息已保存') ||
    line.includes('Storage') ||
    line.includes('语音识别:') ||
    line.includes('槽位提取:') ||
    line.includes('MCP调用:') ||
    line.includes('TTS合成:')
  );

  const visibleLines = storageIndex >= 0 ? lines.slice(0, storageIndex) : lines;
  const location1 = getValueAfterLabel(visibleLines, ['你的位置', '我的位置', '我位置']);
  const location2 = getValueAfterLabel(visibleLines, ['朋友位置', '朋友的位置', '对方位置', '对方的位置']);

  const recommendationStart = visibleLines.findIndex(line => line.startsWith('推荐方案:'));
  const recommendationLines = recommendationStart >= 0
    ? visibleLines.slice(recommendationStart + 1)
    : visibleLines.filter(line =>
      !line.includes('会面地点推荐') &&
      !line.includes('位置信息') &&
      !line.startsWith('你的位置:') &&
      !line.startsWith('我的位置:') &&
      !line.startsWith('我位置:') &&
      !line.startsWith('朋友位置:') &&
      !line.startsWith('朋友的位置:') &&
      !line.startsWith('对方位置:') &&
      !line.startsWith('对方的位置:')
    );

  return {
    location1,
    location2,
    recommendation: recommendationLines.join('\n').trim() || text.trim(),
  };
}

function getDisplayLocation(primary?: string, formatted?: string) {
  const raw = primary?.trim() || '';
  const normalizedFormatted = formatted?.trim() || '';

  if (!raw) {
    return normalizedFormatted;
  }

  if (!normalizedFormatted || normalizedFormatted.includes(raw)) {
    return raw;
  }

  return `${raw}（${normalizedFormatted}）`;
}

function renderInlineMarkdown(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);

  return parts.map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={`${part}-${index}`}>{part.slice(2, -2)}</strong>;
    }

    return part;
  });
}

export function ResponseDisplay({ textResponse, audioUrl, slots, isLoading, error }: ResponseDisplayProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [analysisStep, setAnalysisStep] = useState(0);

  useEffect(() => {
    if (audioUrl && audioRef.current) {
      // 自动播放音频
      audioRef.current.play()
        .then(() => {
          setIsPlaying(true);
        })
        .catch(error => {
          console.error('自动播放失败:', error);
          // 某些浏览器可能阻止自动播放，需要用户交互
        });
    }
  }, [audioUrl]);

  useEffect(() => {
    if (!isLoading) {
      setAnalysisStep(0);
      return;
    }

    const timer = window.setInterval(() => {
      setAnalysisStep((current) => Math.min(current + 1, analysisSteps.length - 1));
    }, 900);

    return () => window.clearInterval(timer);
  }, [isLoading]);

  const handleAudioEnded = () => {
    setIsPlaying(false);
  };

  const handlePlayPause = () => {
    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause();
        setIsPlaying(false);
      } else {
        audioRef.current.play();
        setIsPlaying(true);
      }
    }
  };

  if (isLoading) {
    const currentStep = analysisSteps[analysisStep];

    return (
      <div className="response-display loading">
        <span className="result-step">第 2 步</span>
        <div className="analysis-copy" key={currentStep.title}>
          <h2>{currentStep.title}</h2>
          <p>{currentStep.description}</p>
        </div>

        <div className="analysis-progress" aria-label="分析进度">
          {analysisSteps.map((step, index) => (
            <div
              className={`analysis-step ${index <= analysisStep ? 'active' : ''} ${index === analysisStep ? 'current' : ''}`}
              key={step.title}
            >
              <span className="analysis-dot">{index + 1}</span>
              <span>{step.title}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="response-display error">
        <span className="error-icon" aria-hidden="true">!</span>
        <p>{error}</p>
      </div>
    );
  }

  if (!textResponse && !audioUrl) {
    return null;
  }

  const parsedResponse = textResponse ? parseMeetingResponse(textResponse) : null;
  const location1 = getDisplayLocation(
    slots?.location1 || parsedResponse?.location1,
    slots?.location1Formatted
  );
  const location2 = getDisplayLocation(
    slots?.location2 || parsedResponse?.location2,
    slots?.location2Formatted
  );

  return (
    <div className="response-display success">
      <div className="response-header">
        <div>
          <span className="eyebrow">第 3 步</span>
          <h2>查看推荐方案</h2>
        </div>
      </div>
      
      {parsedResponse && (
        <div className="meeting-result">
          <section className="result-section result-animate section-route">
            <div className="section-title">路线示意</div>
            <div className="route-visual" aria-label="路线示意图">
              <div className="route-track">
                <div className="route-line"></div>
                <div className="route-point route-start">
                  <span className="route-marker"></span>
                  <strong>{location1 || '未识别'}</strong>
                  <small>你的位置</small>
                </div>
                <div className="route-point route-middle">
                  <span className="route-marker recommended"></span>
                  <strong>推荐点</strong>
                </div>
                <div className="route-point route-end">
                  <span className="route-marker"></span>
                  <strong>{location2 || '未识别'}</strong>
                  <small>朋友位置</small>
                </div>
              </div>
            </div>
          </section>

          <section className="result-section result-animate section-recommendation">
            <div className="section-title">推荐方案</div>
            <div className="recommendation-text">
              {parsedResponse.recommendation.split('\n').map((line, index) => (
                <p key={`${line}-${index}`}>{renderInlineMarkdown(line)}</p>
              ))}
            </div>
          </section>
        </div>
      )}

      {audioUrl && (
        <div className="audio-response result-animate section-audio">
          <div className="audio-controls">
            <button 
              className={`play-button ${isPlaying ? 'playing' : ''}`}
              onClick={handlePlayPause}
              title={isPlaying ? '暂停' : '播放'}
            >
              {isPlaying ? '暂停' : '播放'}
            </button>
            <span className="audio-status">
              {isPlaying ? '正在播放语音回复' : '播放语音回复'}
            </span>
          </div>
          <audio 
            ref={audioRef} 
            src={audioUrl}
            onEnded={handleAudioEnded}
            style={{ display: 'none' }}
          />
        </div>
      )}
    </div>
  );
}
