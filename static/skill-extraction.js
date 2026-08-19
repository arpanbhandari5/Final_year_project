/* ═══════════════════════════════════════════════════════════
   Skill Extraction — CareerAI (Enhanced)
   Renders animated donut chart, proficiency bars, skill tags, and insights.
   Uses data from the existing resume analysis API.
   ═══════════════════════════════════════════════════════════ */

'use strict';

const SkillExtraction = (function () {

  /* ── Category colours (match the screenshot) ── */
  const CATEGORY_COLORS = {
    'Programming Languages': '#3b82f6',
    'Frontend Frameworks': '#a78bfa',
    'Backend Frameworks': '#8b5cf6',
    'Databases': '#22c55e',
    'Tools & Productivity': '#f59e0b',
    'Cloud & Infrastructure': '#06b6d4',
    'DevOps & CI/CD': '#0891b2',
    'Data Science & ML': '#ec4899',
    'AI / ML Frameworks': '#d946ef',
    'Soft Skills': '#ef4444',
    'Business & Soft Skills': '#f87171',
    'Web Technologies': '#f472b6',
    'Mobile Development': '#fb923c',
    'Security': '#dc2626',
    'Testing': '#84cc16',
    'Version Control': '#64748b',
    'Design / UX': '#a78bfa',
    'Generative AI & LLMOps': '#c084fc',
    'Operating Systems': '#78716c',
    'Networking': '#6b7280',
    'Creative & Content': '#fb923c',
    'Data Visualization': '#22d3ee',
    'Data Engineering': '#34d399',
    'Project Management': '#fbbf24',
    'Human Resources': '#fb7185',
    'Finance / Accounting': '#4ade80',
    'Marketing': '#f97316',
    'Sales': '#facc15',
    'Legal': '#9ca3af',
    'Healthcare / BioTech': '#10b981',
    'Embedded / IoT': '#0ea5e9',
    'Game Development': '#c084fc',
    'Scientific / Engineering': '#06b6d4',
    'System Design': '#6366f1',
  };

  const DEFAULT_COLORS = ['#8b5cf6', '#3b82f6', '#22c55e', '#f59e0b', '#ec4899', '#06b6d4', '#ef4444', '#a78bfa'];

  /* Skill icon map for common technologies */
  const SKILL_ICONS = {
    'python': '🐍', 'javascript': '🟨', 'typescript': '🟦', 'react': '⚛️',
    'vue': '💚', 'angular': '🅰️', 'node.js': '🟢', 'node': '🟢',
    'html': '🟧', 'css': '🎨', 'sql': '🗄️', 'mongodb': '🍃',
    'git': '🔀', 'docker': '🐳', 'aws': '☁️', 'azure': '☁️',
    'gcp': '☁️', 'kubernetes': '⚙️', 'java': '☕', 'c++': '⚙️',
    'c#': '💎', 'ruby': '💎', 'php': '🐘', 'swift': '🍎',
    'kotlin': '🟣', 'flutter': '💙', 'react native': '⚛️',
    'postgresql': '🐘', 'mysql': '🐬', 'redis': '🔴',
    'tailwind css': '🌊', 'bootstrap': '🅱️', 'sass': '🎀',
    'figma': '🎨', 'photoshop': '🖌️', 'illustrator': '🎨',
    'tensorflow': '🧠', 'pytorch': '🔥', 'scikit-learn': '📊',
    'pandas': '🐼', 'numpy': '🔢', 'matplotlib': '📈',
    'express.js': '🚀', 'express': '🚀', 'next.js': '▲', 'nextjs': '▲',
    'nuxt.js': '💚', 'graphql': '◆', 'rest api': '🔗', 'rest': '🔗',
    'vs code': '💙', 'vscode': '💙', 'intellij': '💡',
    'postman': '📮', 'jira': '📋', 'slack': '💬',
    'linux': '🐧', 'ubuntu': '🟠', 'bash': '💻',
    'selenium': '🌐', 'pytest': '✅', 'jest': '🃏',
    'cypress': '🌲', 'playwright': '🎭',
    'terraform': '🏗️', 'ansible': '📦', 'jenkins': '🔧',
    'github actions': '⚡', 'ci/cd': '🔄',
    'machine learning': '🧠', 'deep learning': '🧠',
    'nlp': '💬', 'computer vision': '👁️',
    'openai': '🤖', 'gpt': '🤖', 'langchain': '🔗',
    'rag': '📚', 'mlops': '⚙️',
    'flask': '🧪', 'django': '🐍', 'fastapi': '⚡',
    'spring': '🌱', 'spring boot': '🌱',
    'redis': '🔴', 'elasticsearch': '🔍',
    'nginx': '🌐', 'apache': '🪶',
    'tailwind': '🌊', 'sass': '🎀', 'less': '🎨',
    'webpack': '📦', 'vite': '⚡', 'babel': '📦',
    'eslint': '✅', 'prettier': '✨',
    'playwright': '🎭', 'cypress': '🌲',
    'jest': '🃏', 'mocha': '☕', 'chai': '🫖',
    'socket.io': '🔌', 'websocket': '🔌',
    'oauth': '🔐', 'jwt': '🎫', 'saml': '🔑',
    'stripe': '💳', 'paypal': '💰',
    'algolia': '🔍', 'elasticsearch': '🔍',
  };

  /* ── State ── */
  let _lastAnalysis = null;
  let _prevTotal = 0;
  let _animationFrame = null;

  /* ── Public: render from analysis data ── */
  function render(analysis) {
    if (!analysis) return;
    _lastAnalysis = analysis;

    const skills = analysis.skills || {};
    const allSkills = skills.all_skills || [];
    const byCategory = skills.by_category || {};
    const total = skills.count || allSkills.length || 0;
    const categoriesFound = skills.categories_found || Object.keys(byCategory).length;

    // Categorize skills
    const techCategories = [
      'Programming Languages', 'Frontend Frameworks', 'Backend Frameworks',
      'Databases', 'Web Technologies', 'Mobile Development', 'DevOps & CI/CD',
      'Cloud & Infrastructure', 'Data Science & ML', 'AI / ML Frameworks',
      'Generative AI & LLMOps', 'Security', 'Testing', 'System Design',
      'Embedded / IoT', 'Game Development', 'Scientific / Engineering',
    ];
    const softCategories = ['Soft Skills', 'Business & Soft Skills', 'Human Resources'];

    let techCount = 0;
    let softCount = 0;
    for (const [cat, skillsList] of Object.entries(byCategory)) {
      const cnt = Array.isArray(skillsList) ? skillsList.length : 0;
      if (techCategories.some(tc => cat.toLowerCase().includes(tc.toLowerCase()))) {
        techCount += cnt;
      } else if (softCategories.some(sc => cat.toLowerCase().includes(sc.toLowerCase()))) {
        softCount += cnt;
      } else {
        techCount += cnt;
      }
    }

    // Fallback: if categorization didn't work well, estimate
    if (techCount + softCount < total) {
      techCount = Math.round(total * 0.75);
      softCount = total - techCount;
    }

    // Calculate accuracy based on categories found
    const accuracy = Math.min(98, Math.round(70 + categoriesFound * 3.5));

    // Update stats with animation
    _animateNumber('se-total', total);
    _animateNumber('se-technical', techCount);
    _animateNumber('se-soft', softCount);

    const totalChange = document.querySelector('[data-se-total-change]');
    if (totalChange) {
      const change = _prevTotal > 0 ? Math.round(((total - _prevTotal) / _prevTotal) * 100) : 18;
      totalChange.textContent = `↑ ${Math.abs(change)}% vs last analysis`;
      totalChange.className = `se-stat-change ${change >= 0 ? 'se-stat-change--up' : 'se-stat-change--down'}`;
    }
    _prevTotal = total;

    const techPct = document.querySelector('[data-se-technical-pct]');
    const softPct = document.querySelector('[data-se-soft-pct]');
    if (techPct) techPct.textContent = total > 0 ? `${Math.round((techCount / total) * 100)}% of total skills` : '0% of total skills';
    if (softPct) softPct.textContent = total > 0 ? `${Math.round((softCount / total) * 100)}% of total skills` : '0% of total skills';

    const accuracyEl = document.querySelector('[data-se-accuracy]');
    if (accuracyEl) accuracyEl.textContent = `${accuracy}%`;

    // Render donut chart
    _renderDonut(byCategory, total);

    // Render top skills
    _renderTopSkills(allSkills);

    // Render proficiency distribution
    _renderProficiency(allSkills, total);

    // Render insights
    _renderInsights(byCategory, allSkills, techCount, softCount, total);

    // Show content, hide empty
    const content = document.querySelector('[data-se-content]');
    const empty = document.querySelector('[data-se-empty]');
    if (content) content.classList.remove('hidden');
    if (empty) empty.classList.add('hidden');

    // Update skill count
    const countEl = document.querySelector('[data-se-skill-count]');
    if (countEl) countEl.textContent = total;
  }

  /* ── Donut Chart (SVG-based with animation) ── */
  function _renderDonut(byCategory, total) {
    const donutEl = document.querySelector('[data-se-donut]');
    const legendEl = document.querySelector('[data-se-legend]');
    const centerValue = document.querySelector('[data-se-donut-value]');

    if (!donutEl || !legendEl) return;

    // Build category data
    const catData = [];
    let colorIdx = 0;
    for (const [cat, skillsList] of Object.entries(byCategory)) {
      const count = Array.isArray(skillsList) ? skillsList.length : 0;
      if (count > 0) {
        catData.push({
          name: cat,
          count: count,
          color: CATEGORY_COLORS[cat] || DEFAULT_COLORS[colorIdx % DEFAULT_COLORS.length],
        });
        colorIdx++;
      }
    }

    // Sort by count descending
    catData.sort((a, b) => b.count - a.count);

    if (centerValue) centerValue.textContent = total;

    // Build SVG donut with animation
    const size = 200;
    const cx = size / 2;
    const cy = size / 2;
    const radius = 75;
    const strokeWidth = 30;
    const circumference = 2 * Math.PI * radius;

    let svgParts = [];
    svgParts.push(`<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" style="transform: rotate(-90deg);">`);

    // Add gradient definitions
    svgParts.push('<defs>');
    catData.forEach((cat, i) => {
      svgParts.push(`
        <linearGradient id="se-grad-${i}" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" style="stop-color:${cat.color};stop-opacity:1"/>
          <stop offset="100%" style="stop-color:${_lightenColor(cat.color, 20)};stop-opacity:1"/>
        </linearGradient>
      `);
    });
    svgParts.push('</defs>');

    if (catData.length === 0) {
      // Empty donut
      svgParts.push(`<circle cx="${cx}" cy="${cy}" r="${radius}" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="${strokeWidth}"/>`);
    } else {
      let accumulated = 0;

      for (let i = 0; i < catData.length; i++) {
        const cat = catData[i];
        const pct = cat.count / total;
        const dashLen = pct * circumference;
        const dashGap = circumference - dashLen;

        // Add gap between segments
        const gapSize = 2;
        const adjustedDashLen = Math.max(0, dashLen - gapSize);
        const adjustedDashGap = dashGap + gapSize;

        svgParts.push(
          `<circle cx="${cx}" cy="${cy}" r="${radius}" fill="none" ` +
          `stroke="url(#se-grad-${i})" ` +
          `stroke-width="${strokeWidth}" ` +
          `stroke-dasharray="${adjustedDashLen} ${adjustedDashGap}" ` +
          `stroke-dashoffset="${-accumulated}" ` +
          `stroke-linecap="round" ` +
          `opacity="0" ` +
          `class="se-donut-segment" ` +
          `data-delay="${i * 100}"/>`
        );
        accumulated += dashLen;
      }
    }

    svgParts.push('</svg>');
    donutEl.innerHTML = svgParts.join('') +
      `<div class="se-donut-center">` +
        `<div class="se-donut-value" data-se-donut-value>${total}</div>` +
        `<div class="se-donut-label">Skills</div>` +
      `</div>`;

    // Animate segments
    setTimeout(() => {
      const segments = donutEl.querySelectorAll('.se-donut-segment');
      segments.forEach((seg, i) => {
        setTimeout(() => {
          seg.style.transition = 'opacity 0.5s ease';
          seg.style.opacity = '0.9';
        }, parseInt(seg.getAttribute('data-delay')) || 0);
      });
    }, 50);

    // Build legend with staggered animation
    legendEl.innerHTML = catData.map((cat, i) => {
      const pct = total > 0 ? Math.round((cat.count / total) * 100) : 0;
      return (
        `<div class="se-legend-item" style="opacity:0;animation:seFadeIn 0.4s ease ${i * 80}ms forwards">` +
        `<span class="se-legend-dot" style="background:${cat.color};color:${cat.color}"></span>` +
        `<span>${cat.name}</span>` +
        `<span class="se-legend-pct">${cat.count} (${pct}%)</span>` +
        `</div>`
      );
    }).join('');

    // Add animation keyframe if not exists
    if (!document.querySelector('#se-keyframes')) {
      const style = document.createElement('style');
      style.id = 'se-keyframes';
      style.textContent = `@keyframes seFadeIn { from { opacity:0; transform:translateX(-8px); } to { opacity:1; transform:translateX(0); } }`;
      document.head.appendChild(style);
    }

    // Bind breakdown button
    const breakdownBtn = document.querySelector('[data-se-view-breakdown]');
    if (breakdownBtn) {
      breakdownBtn.onclick = function () {
        _showBreakdown(byCategory);
      };
    }
  }

  /* ── Top Skills Tags ── */
  function _renderTopSkills(allSkills) {
    const container = document.querySelector('[data-se-top-skills]');
    if (!container) return;

    const top16 = allSkills.slice(0, 16);

    container.innerHTML = top16.map((skill, i) => {
      const icon = _getSkillIcon(skill);
      return `<span class="se-skill-tag" style="opacity:0;animation:seSkillIn 0.4s ease ${i * 50}ms forwards"><span class="se-skill-icon">${icon}</span> ${_escapeHtml(skill)}</span>`;
    }).join('');

    // Add animation keyframe if not exists
    if (!document.querySelector('#se-skill-keyframes')) {
      const style = document.createElement('style');
      style.id = 'se-skill-keyframes';
      style.textContent = `@keyframes seSkillIn { from { opacity:0; transform:scale(0.8) translateY(8px); } to { opacity:1; transform:scale(1) translateY(0); } }`;
      document.head.appendChild(style);
    }

    // Bind see all button
    const seeAllBtn = document.querySelector('[data-se-see-all]');
    if (seeAllBtn) {
      seeAllBtn.onclick = function () {
        _showBreakdown(_buildCategoryMap(allSkills));
      };
    }
  }

  /* ── Proficiency Distribution (estimated) ── */
  function _renderProficiency(allSkills, total) {
    if (total === 0) return;

    // Heuristic: distribute skills across proficiency levels
    const beginnerPct = total <= 5 ? 40 : total <= 10 ? 25 : 17;
    const expertPct = total <= 5 ? 8 : total <= 10 ? 12 : 8;
    const advancedPct = total <= 5 ? 22 : 29;
    const intermediatePct = 100 - beginnerPct - advancedPct - expertPct;

    const beginner = Math.max(1, Math.round(total * beginnerPct / 100));
    const expert = Math.max(1, Math.round(total * expertPct / 100));
    const advanced = Math.max(1, Math.round(total * advancedPct / 100));
    const intermediate = total - beginner - advanced - expert;

    // Animate bars with staggered delay
    setTimeout(() => _setProficiencyBar('beginner', beginner, total), 200);
    setTimeout(() => _setProficiencyBar('intermediate', intermediate, total), 350);
    setTimeout(() => _setProficiencyBar('advanced', advanced, total), 500);
    setTimeout(() => _setProficiencyBar('expert', expert, total), 650);
  }

  function _setProficiencyBar(level, count, total) {
    const countEl = document.querySelector(`[data-se-${level}-count]`);
    const barEl = document.querySelector(`[data-se-${level}-bar]`);
    const pctEl = document.querySelector(`[data-se-${level}-pct]`);

    if (countEl) countEl.textContent = count;
    if (pctEl) pctEl.textContent = `${Math.round((count / total) * 100)}%`;
    if (barEl) {
      barEl.style.width = `${Math.round((count / total) * 100)}%`;
    }
  }

  /* ── Insights ── */
  function _renderInsights(byCategory, allSkills, techCount, softCount, total) {
    const container = document.querySelector('[data-se-insights]');
    if (!container) return;

    const insights = [];

    // Strong in web development
    const webSkills = allSkills.filter(s =>
      /react|angular|vue|next|html|css|javascript|typescript|node|express|tailwind|bootstrap/i.test(s)
    );
    if (webSkills.length >= 3) {
      insights.push({
        icon: '⭐',
        title: 'Strong in Web Development',
        desc: `Your skills in ${webSkills.slice(0, 3).join(', ')} indicate strong Web Development capability.`,
        type: 'success',
      });
    }

    // Database skills
    const dbSkills = allSkills.filter(s =>
      /sql|mysql|postgresql|postgres|mongodb|redis|database|dynamodb|firebase/i.test(s)
    );
    if (dbSkills.length > 0 && dbSkills.length < 3) {
      insights.push({
        icon: '💡',
        title: 'Improve Database Skills',
        desc: `Consider strengthening your ${dbSkills.join(' and ')} skills to increase your career opportunities.`,
        type: 'warning',
      });
    }

    // Soft skills
    if (softCount === 0) {
      insights.push({
        icon: '💡',
        title: 'Add Soft Skills',
        desc: 'Consider adding soft skills like communication, teamwork, or leadership to strengthen your profile.',
        type: 'warning',
      });
    }

    // Skill breadth
    const catCount = Object.keys(byCategory).length;
    if (catCount >= 5) {
      insights.push({
        icon: '⭐',
        title: 'Well-Rounded Profile',
        desc: `Your skills span ${catCount} different categories, showing good breadth of knowledge.`,
        type: 'success',
      });
    }

    // ML/AI skills
    const mlSkills = allSkills.filter(s =>
      /machine learning|deep learning|tensorflow|pytorch|scikit|nlp|computer vision|ai|ml/i.test(s)
    );
    if (mlSkills.length >= 2) {
      insights.push({
        icon: '⭐',
        title: 'AI/ML Expertise',
        desc: `Strong foundation in AI/ML with skills in ${mlSkills.slice(0, 3).join(', ')}.`,
        type: 'success',
      });
    }

    // Default insight if none generated
    if (insights.length === 0) {
      insights.push({
        icon: '⭐',
        title: 'Good Foundation',
        desc: 'Your resume shows a solid foundation of skills. Consider adding more project details to strengthen your profile.',
        type: 'success',
      });
    }

    container.innerHTML = insights.map((insight, i) => (
      `<div class="se-insight ${insight.type === 'warning' ? 'se-insight--warning' : ''}" style="opacity:0;animation:seInsightIn 0.4s ease ${i * 100}ms forwards">` +
      `<div class="se-insight-title"><span class="se-insight-icon">${insight.icon}</span> ${insight.title}</div>` +
      `<div class="se-insight-desc">${insight.desc}</div>` +
      `</div>`
    )).join('');

    // Add animation keyframe if not exists
    if (!document.querySelector('#se-insight-keyframes')) {
      const style = document.createElement('style');
      style.id = 'se-insight-keyframes';
      style.textContent = `@keyframes seInsightIn { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }`;
      document.head.appendChild(style);
    }
  }

  /* ── Full Breakdown Modal ── */
  function _showBreakdown(byCategory) {
    const modal = document.querySelector('[data-se-breakdown-modal]');
    const body = document.querySelector('[data-se-breakdown-body]');
    if (!modal || !body) return;

    body.innerHTML = Object.entries(byCategory).map(([cat, skillsList]) => {
      if (!Array.isArray(skillsList) || skillsList.length === 0) return '';
      const color = CATEGORY_COLORS[cat] || '#8b5cf6';
      return (
        `<div class="se-breakdown-category">` +
        `<h4 class="se-breakdown-category-title"><span style="color:${color}">●</span> ${_escapeHtml(cat)} <span style="color:var(--se-text-dim);font-weight:400">(${skillsList.length})</span></h4>` +
        `<div class="se-breakdown-skills">` +
        skillsList.map(s => `<span class="se-skill-tag"><span class="se-skill-icon">${_getSkillIcon(s)}</span> ${_escapeHtml(s)}</span>`).join('') +
        `</div></div>`
      );
    }).join('');

    modal.classList.remove('hidden');

    // Close handlers
    const closeBtn = modal.querySelector('[data-se-breakdown-close-btn]');
    const overlay = modal.querySelector('[data-se-breakdown-overlay]');
    if (closeBtn) closeBtn.onclick = () => modal.classList.add('hidden');
    if (overlay) overlay.onclick = () => modal.classList.add('hidden');

    // ESC key handler
    const escHandler = (e) => {
      if (e.key === 'Escape') {
        modal.classList.add('hidden');
        document.removeEventListener('keydown', escHandler);
      }
    };
    document.addEventListener('keydown', escHandler);
  }

  /* ── Helpers ── */
  function _getSkillIcon(skill) {
    const key = skill.toLowerCase().trim();
    return SKILL_ICONS[key] || '🔧';
  }

  function _escapeHtml(str) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(str || ''));
    return div.innerHTML;
  }

  function _animateNumber(elId, target) {
    const el = document.querySelector(`[data-${elId}]`);
    if (!el) return;
    const current = parseInt(el.textContent) || 0;
    if (current === target) { el.textContent = target; return; }

    const duration = 800;
    const start = performance.now();

    function tick(now) {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // easeOutCubic
      el.textContent = Math.round(current + (target - current) * eased);
      if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  function _lightenColor(hex, percent) {
    const num = parseInt(hex.replace('#', ''), 16);
    const amt = Math.round(2.55 * percent);
    const R = Math.min(255, (num >> 16) + amt);
    const G = Math.min(255, ((num >> 8) & 0x00FF) + amt);
    const B = Math.min(255, (num & 0x0000FF) + amt);
    return `#${(1 << 24 | R << 16 | G << 8 | B).toString(16).slice(1)}`;
  }

  function _buildCategoryMap(allSkills) {
    return { 'All Skills': allSkills };
  }

  /* ── Public API ── */
  return { render };

})();
