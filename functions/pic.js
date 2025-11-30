// 兼容 EdgeOne Pages 和 Cloudflare Pages
export async function onRequest(context) {
  return handleRequest(context.request);
}

// 缓存
let countData = null;

async function loadCount(request) {
  if (countData) return countData;
  
  try {
    const url = new URL(request.url);
    const resp = await fetch(`${url.origin}/ri/count.json`);
    if (resp.ok) {
      countData = await resp.json();
      return countData;
    }
  } catch (e) {
    console.error('Failed to load count.json:', e);
  }
  return { vd: 0, vl: 0, hd: 0, hl: 0 };
}

function isMobileDevice(userAgent) {
  if (!userAgent) return false;
  const mobileKeywords = [
    'Mobile', 'Android', 'iPhone', 'iPad', 'iPod', 'BlackBerry', 
    'Windows Phone', 'Opera Mini', 'IEMobile', 'Mobile Safari',
    'webOS', 'Kindle', 'Silk', 'Fennec', 'Maemo', 'Tablet'
  ];
  const lowerUA = userAgent.toLowerCase();
  return mobileKeywords.some(k => lowerUA.includes(k.toLowerCase()));
}

async function handleRequest(request) {
  try {
    const url = new URL(request.url);
    const imgType = url.searchParams.get('img');
    const jsonType = url.searchParams.get('json');
    const count = await loadCount(request);

    // ========== JSON 模式 ==========
    if (jsonType === 'h' || jsonType === 'v') {
      const darkFolder = jsonType + 'd';
      const lightFolder = jsonType + 'l';
      const darkCount = count[darkFolder] || 0;
      const lightCount = count[lightFolder] || 0;
      const total = darkCount + lightCount;
      
      if (total === 0) {
        return new Response(JSON.stringify({ error: '没有图片' }), {
          status: 404,
          headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
        });
      }
      
      const randomNum = Math.floor(Math.random() * total) + 1;
      let folder, fileNum, theme;
      
      if (randomNum <= darkCount) {
        folder = darkFolder;
        fileNum = randomNum;
        theme = 'dark';
      } else {
        folder = lightFolder;
        fileNum = randomNum - darkCount;
        theme = 'light';
      }
      
      return new Response(JSON.stringify({
        theme: theme,
        url: url.origin + '/ri/' + folder + '/' + fileNum + '.webp'
      }), {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
          'Cache-Control': 'no-cache, no-store',
          'Access-Control-Allow-Origin': '*'
        }
      });
    }

    // ========== 重定向模式 ==========
    let orientation;
    if (imgType === 'h') {
      orientation = 'h';
    } else if (imgType === 'v') {
      orientation = 'v';
    } else {
      // 无参数 或 img=ua 都自动检测
      const userAgent = request.headers.get('User-Agent') || '';
      orientation = isMobileDevice(userAgent) ? 'v' : 'h';
    }
    
    const darkFolder = orientation + 'd';
    const lightFolder = orientation + 'l';
    const darkCount = count[darkFolder] || 0;
    const lightCount = count[lightFolder] || 0;
    const total = darkCount + lightCount;
    
    if (total === 0) {
      return new Response('没有图片', {
        status: 404,
        headers: { 'Content-Type': 'text/plain; charset=utf-8', 'Access-Control-Allow-Origin': '*' }
      });
    }
    
    const randomNum = Math.floor(Math.random() * total) + 1;
    let folder, fileNum;
    
    if (randomNum <= darkCount) {
      folder = darkFolder;
      fileNum = randomNum;
    } else {
      folder = lightFolder;
      fileNum = randomNum - darkCount;
    }
    
    return new Response(null, {
      status: 302,
      headers: {
        'Location': '/ri/' + folder + '/' + fileNum + '.webp',
        'Cache-Control': 'no-cache',
        'Access-Control-Allow-Origin': '*'
      }
    });

  } catch (error) {
    return new Response('错误: ' + error.message, {
      status: 500,
      headers: { 'Content-Type': 'text/plain; charset=utf-8' }
    });
  }
}
