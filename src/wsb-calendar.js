import { state, API_BASE } from './state.js';
import { translations, onLanguageChange } from './i18n.js';

export async function loadWsbCalendar(force = false) {
    if (state.currentWsbCalendar && !force) return;

    const tbody = document.getElementById('wsb-calendar-table-body');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="3" style="text-align: center; color: var(--text-muted);">${translations[state.activeLang].loading_wsb_calendar}</td></tr>`;

    try {
        const res = await fetch(`${API_BASE}/api/wsb-calendar`);
        if (!res.ok) throw new Error(`API error: ${res.status}`);
        const payload = await res.json();
        state.currentWsbCalendar = payload.data || { zh: [], en: [] };
        renderWsbCalendar(state.currentWsbCalendar);
    } catch (error) {
        console.error('Failed to load WSB calendar:', error);
        tbody.innerHTML = `<tr><td colspan="3" style="text-align: center; color: var(--negative);">${translations[state.activeLang].err_wsb_calendar}</td></tr>`;
    }
}

export function renderWsbCalendar(calendar) {
    const tbody = document.getElementById('wsb-calendar-table-body');
    if (!tbody) return;
    tbody.innerHTML = '';

    const list = calendar[state.activeLang] || [];
    if (list.length === 0) {
        tbody.innerHTML = `<tr><td colspan="3" style="text-align: center; color: var(--text-muted);">No calendar events found. / 暂无重要事件。</td></tr>`;
        return;
    }

    list.forEach(item => {
        const tr = document.createElement('tr');

        const dateTd = document.createElement('td');
        dateTd.className = 'font-mono';
        dateTd.style.fontWeight = '600';
        dateTd.style.color = 'var(--primary)';
        dateTd.textContent = item.date || '-';

        const eventTd = document.createElement('td');
        eventTd.style.fontWeight = '500';
        eventTd.textContent = item.event || '-';

        const focusTd = document.createElement('td');
        focusTd.style.color = 'var(--text-muted)';
        focusTd.textContent = item.focus || '-';

        tr.appendChild(dateTd);
        tr.appendChild(eventTd);
        tr.appendChild(focusTd);

        tbody.appendChild(tr);
    });
}

onLanguageChange(() => {
    if (state.currentWsbCalendar) {
        renderWsbCalendar(state.currentWsbCalendar);
    }
});
