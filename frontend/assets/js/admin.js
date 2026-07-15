const statusGrid = document.getElementById('statusGrid');
    const cookieInput = document.getElementById('cookieInput');
    const saveButton = document.getElementById('saveButton');
    const message = document.getElementById('message');

    function setMessage(text, type = '') {
      message.hidden = false;
      message.className = `message ${type}`;
      message.textContent = text;
    }

    async function loadStatus() {
      try {
        const res = await fetch('/api/health', { cache: 'no-store' });
        const payload = await res.json();
        const status = payload.status || {};
        statusGrid.innerHTML = `
          <div class="status-item">
            <div class="label">Cookie</div>
            <div class="value">${payload.cookie?.configured ? '已配置' : '未配置'}</div>
          </div>
          <div class="status-item">
            <div class="label">来源</div>
            <div class="value">${payload.cookie?.source || '--'}</div>
          </div>
          <div class="status-item">
            <div class="label">最近状态</div>
            <div class="value">${status.ok ? '成功' : (status.last_error?.message || '暂无成功记录')}</div>
          </div>
        `;
      } catch (error) {
        setMessage(`健康检查失败：${error.message}`, 'error');
      }
    }

    saveButton.addEventListener('click', async () => {
      const cookie = cookieInput.value.trim();
      if (!cookie) {
        setMessage('Cookie 不能为空', 'error');
        return;
      }

      saveButton.disabled = true;
      setMessage('正在验证 Cookie，请稍候');
      try {
        const res = await fetch('/api/admin/cookie', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ cookie })
        });
        const payload = await res.json();
        if (!res.ok || !payload.ok) {
          throw new Error(payload.error?.message || `HTTP ${res.status}`);
        }
        cookieInput.value = '';
        setMessage(`${payload.message}。${payload.warning}`, 'ok');
        await loadStatus();
      } catch (error) {
        setMessage(`更新失败：${error.message}`, 'error');
      } finally {
        saveButton.disabled = false;
      }
    });

    loadStatus();
