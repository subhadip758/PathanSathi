// app.js - dark mode, instant search (AJAX), and chat helper
(function(){
  // --- Dark mode toggle ---
  const btn = document.getElementById('darkToggle');
  const setTheme = (t)=> {
    if(t==='dark') {
      document.documentElement.setAttribute('data-theme','dark');
      if(btn) btn.textContent = '☀️';
    } else {
      document.documentElement.removeAttribute('data-theme');
      if(btn) btn.textContent = '🌙';
    }
    try{ localStorage.setItem('theme',t); }catch(e){}
  };
  const cur = (function(){ try{ return localStorage.getItem('theme')||'light'}catch(e){return 'light'} })();
  setTheme(cur);
  if(btn) btn.addEventListener('click', ()=> setTheme((localStorage.getItem('theme')==='dark') ? 'light' : 'dark'));

  // --- Helpers ---
  function qs(sel){ return document.querySelector(sel); }
  function qsa(sel){ return Array.from(document.querySelectorAll(sel)); }

  // --- Instant search (AJAX) ---
  const qInput = document.getElementById('q');
  const authorInput = document.getElementById('author');
  const genreInput = document.getElementById('genre');
  const resultsList = document.getElementById('resultsList');
  const searchBtn = document.getElementById('searchBtn');

  // render results object {title: copies}
  function renderResults(results){
    if(!resultsList) return;
    resultsList.innerHTML = '';
    if(!results || Object.keys(results).length===0){
      resultsList.innerHTML = '<li class="list-group-item">No results</li>';
      return;
    }
    for(const [title, copies] of Object.entries(results)){
      // attempt to get author/genre from existing DOM (if available)
      let author = '';
      let genre = '';
      const existing = document.querySelector('[data-title]') && document.querySelector(`[data-title="${CSS.escape(title)}"]`);
      if(existing){
        author = existing.getAttribute('data-author') || '';
        genre = existing.getAttribute('data-genre') || '';
      }
      const li = document.createElement('li');
      li.className = 'list-group-item d-flex justify-content-between align-items-center';
      li.innerHTML = `<div><strong class="book-title">${title}</strong><br><small class="book-author">${author}</small> — <small class="book-genre">${genre}</small></div><span class="badge rounded-pill">${copies}</span>`;
      resultsList.appendChild(li);
    }
  }

  // perform AJAX GET to /search
  let debounceTimer = null;
  function doSearch(){
    const q = qInput? qInput.value.trim() : '';
    const author = authorInput? authorInput.value.trim() : '';
    const genre = genreInput? genreInput.value.trim() : '';
    const params = new URLSearchParams({ q:q, author:author, genre:genre });
    fetch('/search?'+params.toString())
      .then(r=> r.ok? r.json() : Promise.reject('network'))
      .then(data => renderResults(data))
      .catch(err => { console.error('Search error', err); });
  }

  // debounce wrapper
  function scheduleSearch(){
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(doSearch, 250);
  }

  [qInput, authorInput, genreInput].forEach(el=>{
    if(el) el.addEventListener('input', scheduleSearch);
  });

  if(searchBtn){
    searchBtn.addEventListener('click', (e)=>{
      e.preventDefault();
      doSearch();
    });
  }

  // --- Chat assistant ---
  const chatBtn = document.getElementById('chatBtn');
  const chatQ = document.getElementById('chatQ');
  const chatResp = document.getElementById('chatResp');

  if(chatBtn && chatQ && chatResp){
    chatBtn.addEventListener('click', ()=>{
      const q = chatQ.value.trim();
      if(!q){ chatResp.textContent = 'Please type a question.'; return; }
      chatResp.textContent = 'Thinking...';
      fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ q: q })
      }).then(r=> r.ok? r.json() : Promise.reject('network'))
        .then(data => {
          if(data && data.reply) chatResp.textContent = data.reply;
          else chatResp.textContent = 'No reply returned.';
        }).catch(err=>{
          console.error('Chat error', err);
          chatResp.textContent = 'Error contacting the assistant.';
        });
    });
  }

})();