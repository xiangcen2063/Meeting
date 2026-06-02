const API_BASE = '/api';

export interface MeetingResponse {
  success: boolean;
  audioUrl?: string;
  textResponse?: string;
  error?: string;
  slots?: {
    location1?: string;
    location2?: string;
    city?: string;
    location1Formatted?: string;
    location2Formatted?: string;
  };
}

export async function sendVoiceForMeetingPoint(audioBlob: Blob): Promise<MeetingResponse> {
  const formData = new FormData();
  formData.append('audio', audioBlob, 'recording.webm');

  const response = await fetch(`${API_BASE}/meeting/recommend`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}

export async function sendTextForMeetingPoint(text: string): Promise<MeetingResponse> {
  const response = await fetch(`${API_BASE}/meeting/recommend-text`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ text }),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}
