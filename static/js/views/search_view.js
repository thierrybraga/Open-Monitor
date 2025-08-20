// search_view.js
// Responsável por renderizar resultados de busca e manipular eventos de pesquisa

const SearchView = (() => {
    let container;
    let form;
    let inputField;
    let searchModel;
    let debounceTimer;
    let isInitialized = false;

    // Lazy loading do modelo
    async function loadModel() {
        if (!searchModel) {
            const { default: SearchModel } = await import("../models/search_model.js");
            searchModel = SearchModel;
        }
        return searchModel;
    }

    function init() {
        if (isInitialized) return;
        
        container = document.getElementById("search-results-container");
        form = document.getElementById("search-form");
        inputField = document.getElementById("search-input");
        bindEvents();
        isInitialized = true;
    }

    // Debounce para eventos de busca
    function debounce(func, wait) {
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(debounceTimer);
                func(...args);
            };
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(later, wait);
        };
    }

    /**
     * Renderiza a lista de resultados de busca.
     * @param {Array<Object>} results - Lista de objetos com campos:
     *   {number} id
     *   {string} title
     *   {string} summary
     */
    function render(results) {
        if (!container) init();

        if (!results || results.length === 0) {
            container.innerHTML = `<p>Nenhum resultado encontrado.</p>`;
            return;
        }

        const items = results.map(item => `
            <div class="search-result card mb-3" data-id="${item.id}">
                <div class="card-body">
                    <h5 class="card-title">${item.title}</h5>
                    <p class="card-text">${item.summary}</p>
                    <button class="btn btn-sm btn-primary view-result-btn">Ver Detalhes</button>
                </div>
            </div>
        `).join('');

        container.innerHTML = items;
        bindDetailButtons();
    }

    /**
     * Limpa os resultados exibidos.
     */
    function clear() {
        if (!container) init();
        container.innerHTML = "";
    }

    /**
     * Associa eventos ao formulário e botões de detalhes com debounce.
     */
    function bindEvents() {
        if (!form || !inputField) return;
        
        const debouncedSearch = debounce((query) => {
            document.dispatchEvent(
                new CustomEvent("search:execute", { detail: { query } })
            );
        }, 300);
        
        form.addEventListener("submit", (e) => {
            e.preventDefault();
            const query = inputField.value.trim();
            if (!query) return;
            debouncedSearch(query);
        });
        
        // Busca em tempo real enquanto digita
        inputField.addEventListener('input', debounce(() => {
            const query = inputField.value.trim();
            if (query.length >= 3) {
                debouncedSearch(query);
            }
        }, 500));
    }

    /**
     * Adiciona listener aos botões de ver detalhes.
     */
    function bindDetailButtons() {
        const buttons = document.querySelectorAll(".view-result-btn");
        buttons.forEach(btn => {
            btn.addEventListener("click", (e) => {
                const id = e.target.closest('.search-result').dataset.id;
                document.dispatchEvent(
                    new CustomEvent("search:view", { detail: { id } })
                );
            });
        });
    }

    /**
     * Limpa recursos e event listeners para evitar memory leaks.
     */
    function cleanup() {
        if (debounceTimer) {
            clearTimeout(debounceTimer);
        }
        
        container = null;
        form = null;
        inputField = null;
        searchModel = null;
        isInitialized = false;
    }

    return {
        render,
        clear,
        cleanup,
        init
    };
})();

let map;
function initMap() {
    map = new google.maps.Map(document.getElementById('map'), {
        center: { lat: 0, lng: 0 },
        zoom: 2
    });
}

document.addEventListener('DOMContentLoaded', () => {
    const searchForm = document.getElementById('search-form');
    const searchInput = document.getElementById('search-ip');
    const searchBtn = document.getElementById('search-btn');
    const clearBtn = document.getElementById('clear-form');
    const errorDiv = document.getElementById('ip-error');
    const resultSection = document.getElementById('result-section');
    const tableBody = document.getElementById('result-table-body');
    const prevPage = document.getElementById('prev-page');
    const nextPage = document.getElementById('next-page');
    const pageInfo = document.getElementById('page-info');
    const goToPage = document.getElementById('go-to-page');
    const pageSize = document.getElementById('page-size');
    const recentSearches = document.getElementById('recent-searches');
    const recentSearchesList = document.getElementById('recent-searches-list');
    const exportBtn = document.getElementById('export-results');
    const resetDemo = document.getElementById('reset-demo');

    let currentPage = 1;
    let currentPageSize = parseInt(pageSize.value);
    let results = [];
    let recent = JSON.parse(localStorage.getItem('recentSearches')) || [];

    // Update recent searches UI
    function updateRecentSearches() {
        recentSearchesList.innerHTML = '';
        recent.forEach(search => {
            const li = document.createElement('li');
            li.className = 'p-2 cursor-pointer hover:bg-gray-100';
            li.textContent = search;
            li.setAttribute('role', 'option');
            li.tabIndex = 0;
            li.addEventListener('click', () => {
                searchInput.value = search;
                recentSearches.classList.add('d-none');
                searchForm.submit();
            });
            li.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    searchInput.value = search;
                    recentSearches.classList.add('d-none');
                    searchForm.submit();
                }
            });
            recentSearchesList.appendChild(li);
        });
        recentSearches.classList.toggle('d-none', recent.length === 0);
    }

    // Form submission
    searchForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const query = searchInput.value.trim();
        if (!query) {
            searchInput.setAttribute('aria-invalid', 'true');
            errorDiv.textContent = 'Por favor, insira um IP ou domínio.';
            errorDiv.classList.add('d-block');
            return;
        }
        searchInput.setAttribute('aria-invalid', 'false');
        errorDiv.textContent = '';
        errorDiv.classList.remove('d-block');

        searchBtn.querySelector('.spinner').classList.remove('d-none');
        searchBtn.querySelector('span').classList.add('d-none');
        searchBtn.disabled = true;

        try {
            // Simulate Shodan API call
            results = [
                { property: 'IP', value: query },
                { property: 'ISP', value: 'Example ISP' },
                { property: 'Organization', value: 'Example Org' },
                { property: 'Ports', value: '80, 443' },
                { property: 'Location', value: 'New York, USA' },
                { property: 'Latitude', value: '40.7128' },
                { property: 'Longitude', value: '-74.0060' }
            ];

            // Update recent searches
            if (!recent.includes(query)) {
                recent.unshift(query);
                recent = recent.slice(0, 5);
                localStorage.setItem('recentSearches', JSON.stringify(recent));
            }
            updateRecentSearches();

            // Update UI
            document.getElementById('summary-ip').textContent = query;
            document.getElementById('summary-isp').textContent = results.find(r => r.property === 'ISP')?.value || 'N/A';
            document.getElementById('summary-org').textContent = results.find(r => r.property === 'Organization')?.value || 'N/A';
            document.getElementById('summary-ports').textContent = results.find(r => r.property === 'Ports')?.value || 'N/A';
            document.getElementById('summary-location').textContent = results.find(r => r.property === 'Location')?.value || 'N/A';
            document.getElementById('demo-badge').classList.add('d-none');
            resultSection.classList.remove('d-none');

            // Update map
            const lat = parseFloat(results.find(r => r.property === 'Latitude')?.value || 0);
            const lng = parseFloat(results.find(r => r.property === 'Longitude')?.value || 0);
            map.setCenter({ lat, lng });
            map.setZoom(10);
            new google.maps.Marker({
                position: { lat, lng },
                map,
                title: query
            });
            document.getElementById('map').setAttribute('aria-label', `Mapa com localização do IP ${query}`);

            // Update table
            renderTable();

        } catch (error) {
            document.getElementById('error-message').classList.remove('d-none');
            document.getElementById('error-text').textContent = error.message || 'Erro ao consultar o IP ou domínio.';
        } finally {
            searchBtn.querySelector('.spinner').classList.add('d-none');
            searchBtn.querySelector('span').classList.remove('d-none');
            searchBtn.disabled = false;
        }
    });

    // Clear form
    clearBtn.addEventListener('click', () => {
        searchForm.reset();
        searchInput.setAttribute('aria-invalid', 'false');
        errorDiv.textContent = '';
        errorDiv.classList.remove('d-block');
        resultSection.classList.add('d-none');
        recentSearches.classList.add('d-none');
    });

    // Render table
    function renderTable() {
        tableBody.innerHTML = '';
        const start = (currentPage - 1) * currentPageSize;
        const end = start + currentPageSize;
        const paginatedResults = results.slice(start, end);

        paginatedResults.forEach(result => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="ps-3">${result.property}</td>
                <td class="ps-3">${result.value}</td>
                <td class="ps-3"></td>
            `;
            tableBody.appendChild(tr);
        });

        const totalPages = Math.ceil(results.length / currentPageSize) || 1;
        pageInfo.textContent = `Página ${currentPage} de ${totalPages}`;
        prevPage.disabled = currentPage <= 1;
        nextPage.disabled = currentPage >= totalPages;
        goToPage.max = totalPages;
    }

    // Pagination controls
    prevPage.addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            renderTable();
        }
    });

    nextPage.addEventListener('click', () => {
        const totalPages = Math.ceil(results.length / currentPageSize);
        if (currentPage < totalPages) {
            currentPage++;
            renderTable();
        }
    });

    goToPage.addEventListener('change', (e) => {
        const page = parseInt(e.target.value);
        const totalPages = Math.ceil(results.length / currentPageSize);
        if (page >= 1 && page <= totalPages) {
            currentPage = page;
            renderTable();
        }
    });

    pageSize.addEventListener('change', (e) => {
        currentPageSize = parseInt(e.target.value);
        currentPage = 1;
        renderTable();
    });

    // Table sorting
    document.querySelectorAll('.sortable').forEach(th => {
        th.addEventListener('click', () => {
            const sortKey = th.dataset.sort;
            results.sort((a, b) => a[sortKey].localeCompare(b[sortKey]));
            renderTable();
        });
    });

    // Export results
    exportBtn.addEventListener('click', () => {
        const csv = results.map(r => `${r.property},${r.value}`).join('\n');
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'shodan_results.csv';
        a.click();
        URL.revokeObjectURL(url);
    });

    // Reset demo
    resetDemo.addEventListener('click', () => {
        searchInput.value = '192.168.0.1';
        searchForm.submit();
    });

    // Show recent searches on focus
    searchInput.addEventListener('focus', () => {
        updateRecentSearches();
    });

    // Hide recent searches on blur
    searchInput.addEventListener('blur', () => {
        setTimeout(() => recentSearches.classList.add('d-none'), 200);
    });
});

export default SearchView;