// JavaScript para o Mesh↔APRS Gateway

// Atualiza estatísticas automaticamente
async function updateStats() {
    try {
        const response = await fetch('/api/stats');
        const stats = await response.json();
        
        // Atualiza elementos se existirem na página
        const elements = {
            'total-operators': stats.operators.total,
            'active-operators': stats.operators.active,
            'total-messages': stats.messages.total,
            'pending-messages': stats.messages.pending
        };
        
        for (const [id, value] of Object.entries(elements)) {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = value;
            }
        }
    } catch (error) {
        console.error('Erro ao atualizar estatísticas:', error);
    }
}

// Formata timestamp para exibição
function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString('pt-BR');
}

// Copia texto para clipboard
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        // Mostra feedback visual
        const toast = document.createElement('div');
        toast.className = 'toast align-items-center text-white bg-success border-0';
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">Copiado para a área de transferência!</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;
        
        document.body.appendChild(toast);
        const bsToast = new bootstrap.Toast(toast);
        bsToast.show();
        
        toast.addEventListener('hidden.bs.toast', () => {
            document.body.removeChild(toast);
        });
    });
}

// Inicialização
document.addEventListener('DOMContentLoaded', function() {
    // Atualiza estatísticas a cada 30 segundos
    if (window.location.pathname === '/') {
        updateStats();
        setInterval(updateStats, 30000);
    }
    
    // Adiciona tooltips do Bootstrap
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Marca item ativo no menu
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
    navLinks.forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        }
    });
});

// Funções utilitárias para API
const API = {
    async get(url) {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    },
    
    async post(url, data) {
        const response = await fetch(url, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || `HTTP ${response.status}`);
        }
        return response.json();
    },
    
    async put(url, data) {
        const response = await fetch(url, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || `HTTP ${response.status}`);
        }
        return response.json();
    },
    
    async delete(url) {
        const response = await fetch(url, {method: 'DELETE'});
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || `HTTP ${response.status}`);
        }
        return response.json();
    }
};
