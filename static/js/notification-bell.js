(function () {
    'use strict';

    function getCookie(name) {
        var match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
        return match ? decodeURIComponent(match[1]) : '';
    }

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function updateBadge(wrap, count) {
        var badge = wrap.querySelector('.notification-bell-badge');
        if (count > 0) {
            if (!badge) {
                badge = document.createElement('span');
                badge.className = 'notification-bell-badge';
                wrap.querySelector('.notification-bell-btn').appendChild(badge);
            }
            badge.textContent = count > 99 ? '99+' : String(count);
            badge.hidden = false;
        } else if (badge) {
            badge.remove();
        }
    }

    function renderNotifications(listEl, items) {
        if (!items.length) {
            listEl.innerHTML = '<div class="notification-dropdown-empty"><i class="bi bi-bell-slash d-block mb-2" style="font-size:1.4rem;opacity:.45;"></i>اعلان جدیدی وجود ندارد.</div>';
            return;
        }

        listEl.innerHTML = items.map(function (item) {
            var unreadClass = item.is_read ? '' : ' unread';
            var unreadDot = item.is_read ? '' : '<span class="notification-dropdown-unread-dot" aria-hidden="true"></span>';
            return (
                '<a href="#" class="notification-dropdown-item type-' + escapeHtml(item.display_type) + unreadClass + '" data-notification-id="' + item.id + '">' +
                    '<span class="notification-dropdown-icon"><i class="bi ' + escapeHtml(item.icon) + '"></i></span>' +
                    '<span class="notification-dropdown-content">' +
                        '<div class="notification-dropdown-title">' +
                            unreadDot +
                            '<span class="notification-dropdown-title-text">' +
                                escapeHtml(item.emoji) + ' ' + escapeHtml(item.title) +
                            '</span>' +
                        '</div>' +
                        '<div class="notification-dropdown-time">' + escapeHtml(item.relative_time) + '</div>' +
                    '</span>' +
                '</a>'
            );
        }).join('');
    }

    function initBell(wrap) {
        var dropdownUrl = wrap.dataset.dropdownUrl;
        var markAllUrl = wrap.dataset.markAllUrl;
        var dashboardUrl = wrap.dataset.dashboardUrl;
        var listEl = wrap.querySelector('.notification-dropdown-list');
        var markAllBtn = wrap.querySelector('.notification-mark-all-btn');
        var bellBtn = wrap.querySelector('.notification-bell-btn');
        var loaded = false;
        var loading = false;

        function loadDropdown(force) {
            if (loading) {
                return;
            }
            if (loaded && !force) {
                return;
            }

            loading = true;
            listEl.innerHTML = '<div class="notification-dropdown-loading"><span class="spinner-border spinner-border-sm ms-2" role="status"></span> در حال بارگذاری...</div>';

            fetch(dropdownUrl, {
                headers: { 'Accept': 'application/json' },
                credentials: 'same-origin',
            })
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error('load failed');
                    }
                    return response.json();
                })
                .then(function (data) {
                    updateBadge(wrap, data.unread_count || 0);
                    renderNotifications(listEl, data.notifications || []);
                    loaded = true;
                })
                .catch(function () {
                    listEl.innerHTML = '<div class="notification-dropdown-empty">بارگذاری اعلان‌ها ممکن نشد.</div>';
                })
                .finally(function () {
                    loading = false;
                });
        }

        bellBtn.addEventListener('show.bs.dropdown', function () {
            loadDropdown(true);
        });

        if (markAllBtn) {
            markAllBtn.addEventListener('click', function (event) {
                event.preventDefault();
                event.stopPropagation();

                markAllBtn.disabled = true;

                fetch(markAllUrl, {
                    method: 'POST',
                    headers: {
                        'Accept': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    credentials: 'same-origin',
                })
                    .then(function (response) {
                        if (!response.ok) {
                            throw new Error('mark all failed');
                        }
                        return response.json();
                    })
                    .then(function (data) {
                        updateBadge(wrap, data.unread_count || 0);
                        listEl.querySelectorAll('.notification-dropdown-item.unread').forEach(function (item) {
                            item.classList.remove('unread');
                            var dot = item.querySelector('.notification-dropdown-unread-dot');
                            if (dot) {
                                dot.remove();
                            }
                        });
                    })
                    .catch(function () {
                        window.location.href = dashboardUrl;
                    })
                    .finally(function () {
                        markAllBtn.disabled = false;
                    });
            });
        }

        listEl.addEventListener('click', function (event) {
            var item = event.target.closest('.notification-dropdown-item');
            if (!item) {
                return;
            }
            event.preventDefault();
            window.location.href = dashboardUrl;
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('.notification-bell-wrap').forEach(initBell);
    });
})();
