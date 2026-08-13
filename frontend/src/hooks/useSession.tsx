import { useEffect, useState } from 'react';

export const useSession = () => {
  const [sessionId, setSessionId] = useState<string>('');
  const [deviceType, setDeviceType] = useState<string>('');
  const [userAgent, setUserAgent] = useState<string>('');

  useEffect(() => {
    // Get or create session ID
    let storedSessionId = sessionStorage.getItem('chat_session_id');
    if (!storedSessionId) {
      storedSessionId = `session_${Date.now()}_${Math.random().toString(36).substring(7)}`;
      sessionStorage.setItem('chat_session_id', storedSessionId);
    }
    setSessionId(storedSessionId);

    // Detect device type
    const ua = navigator.userAgent;
    setUserAgent(ua);

    if (/(tablet|ipad|playbook|silk)|(android(?!.*mobi))/i.test(ua)) {
      setDeviceType('tablet');
    } else if (/Mobile|Android|iP(hone|od)|IEMobile|BlackBerry|Kindle|Silk-Accelerated|(hpw|web)OS|Opera M(obi|ini)/.test(ua)) {
      setDeviceType('mobile');
    } else {
      setDeviceType('desktop');
    }
  }, []);

  return { sessionId, deviceType, userAgent };
};
