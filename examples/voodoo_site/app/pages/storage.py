"""File storage management and object browser."""
from voodoo import Div, Card, Heading, _
from app.layout import Layout

async def page(request):
    content = Div(
        Card(
            Div(
                f"""
                <div class="flex flex-col space-y-6">
                    <div class="relative group">
                        <div class="absolute -inset-0.5 bg-gradient-to-r from-[var(--color-secondary)] to-[var(--color-primary)] rounded-xl blur opacity-30 group-hover:opacity-100 transition duration-1000 group-hover:duration-200"></div>
                        <div class="relative flex flex-col items-center justify-center p-12 bg-[var(--color-background)]/80 border border-[var(--color-border)] rounded-xl">
                            <input type="file" id="file-upload" class="hidden" onchange="document.getElementById('file-name').innerText = this.files[0].name" />
                            <label for="file-upload" class="cursor-pointer flex flex-col items-center justify-center space-y-4">
                                <svg class="w-12 h-12 text-[var(--color-text-muted)] group-hover:text-[var(--color-primary)] transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path></svg>
                                <span class="text-lg font-medium text-[var(--color-text)]">{_('storage.select')}</span>
                                <span id="file-name" class="text-sm text-[var(--color-text-muted)]">{_('storage.no_file')}</span>
                            </label>
                        </div>
                    </div>
                    <button onclick="uploadFile()" class="w-full bg-[var(--color-surface)] hover:bg-[var(--color-surface)] border border-[var(--color-border)] transition-all text-[var(--color-text)] font-bold py-3 px-4 rounded-xl shadow-lg">
                        {_('storage.upload_btn')}
                    </button>
                    <div id="upload-result" class="text-center text-sm font-medium h-6"></div>
                    <script>
                        async function uploadFile() {{
                            const fileInput = document.getElementById('file-upload');
                            const resultDiv = document.getElementById('upload-result');
                            if (!fileInput.files.length) {{
                                resultDiv.innerText = '{_('storage.err_no_file')}';
                                resultDiv.className = 'text-center text-sm font-medium h-6 text-red-400';
                                return;
                            }}
                            const formData = new FormData();
                            formData.append('file', fileInput.files[0]);
                            
                            resultDiv.innerText = '{_('storage.uploading')}';
                            resultDiv.className = 'text-center text-sm font-medium h-6 text-[var(--color-text-muted)] animate-pulse';
                            
                            try {{
                                const response = await fetch('/api/upload', {{
                                    method: 'POST',
                                    body: formData
                                }});
                                const data = await response.json();
                                if (data.url) {{
                                    resultDiv.innerHTML = `{_('storage.success')} <a href="${{data.url}}" target="_blank" class="text-[var(--color-primary)] hover:text-[var(--color-secondary)] transition-colors underline">${{data.url}}</a>`;
                                    resultDiv.className = 'text-center text-sm font-medium h-6 text-green-400';
                                }} else {{
                                    resultDiv.innerText = '{_('storage.error')}' + JSON.stringify(data);
                                    resultDiv.className = 'text-center text-sm font-medium h-6 text-red-400';
                                }}
                            }} catch (e) {{
                                resultDiv.innerText = '{_('storage.failed')}' + e.message;
                                resultDiv.className = 'text-center text-sm font-medium h-6 text-red-400';
                            }}
                        }}
                    </script>
                </div>
                """
            ),
            className="bg-[var(--color-surface)] border-[var(--color-border)] backdrop-blur-md max-w-2xl mx-auto"
        )
    )
    
    return Layout(content, title=_("storage.title"))
