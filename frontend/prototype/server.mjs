import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';

const files = { '/': ['index.html', 'text/html'], '/index.html': ['index.html', 'text/html'], '/styles.css': ['styles.css', 'text/css'], '/app.js': ['app.js', 'text/javascript'] };
files['/design.css'] = ['design.css', 'text/css'];
files['/layouts.js'] = ['layouts.js', 'text/javascript'];
for (const name of ['barlow-condensed-latin-600-normal.woff2', 'ibm-plex-sans-latin-400-normal.woff2', 'ibm-plex-sans-latin-500-normal.woff2']) {
  files[`/fonts/${name}`] = [`fonts/${name}`, 'font/woff2'];
}
const server = createServer(async (request, response) => {
  const file = files[new URL(request.url, 'http://localhost').pathname];
  if (!file) { response.writeHead(404); response.end('Not found'); return; }
  try {
    const body = await readFile(new URL(file[0], import.meta.url));
    response.writeHead(200, { 'Content-Type': `${file[1]}; charset=utf-8`, 'Cache-Control': 'no-store' });
    response.end(body);
  } catch {
    response.writeHead(500); response.end('Prototype file unavailable');
  }
});
server.listen(4173, '127.0.0.1', () => console.log('CompSphere UI prototype: http://127.0.0.1:4173'));
