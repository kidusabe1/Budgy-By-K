"""Visualization utilities for charts (mobile-optimized)."""

import io
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import matplotlib

matplotlib.use('Agg')  # Non-interactive backend for servers
import matplotlib.pyplot as plt
import numpy as np

# Shared palette
_COLORS = [
	'#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
	'#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9', '#F8B500',
]


def _save(fig) -> io.BytesIO:
	"""Save figure to a BytesIO buffer and close it."""
	buf = io.BytesIO()
	fig.savefig(buf, format='png', dpi=180, bbox_inches='tight',
				facecolor='white', edgecolor='none')
	buf.seek(0)
	plt.close(fig)
	return buf


class VisualizationService:
	"""Creates charts for summaries."""

	@staticmethod
	def pie_chart(data: Dict[str, float], title: str) -> Optional[io.BytesIO]:
		if not data:
			return None

		plt.style.use('seaborn-v0_8-whitegrid')

		labels = [cat.split(' ', 1)[1] if ' ' in cat else cat for cat in data.keys()]
		values = list(data.values())
		total = sum(values)

		fig, ax = plt.subplots(figsize=(7, 7))

		wedges, _ = ax.pie(
			values,
			colors=_COLORS[:len(values)],
			startangle=90,
			wedgeprops=dict(width=0.45, edgecolor='white', linewidth=2),
			pctdistance=0.78,
		)

		# Center label
		ax.text(
			0, 0, f'Total\n${total:,.2f}',
			ha='center', va='center',
			fontsize=16, fontweight='bold',
			color='#2c3e50',
		)

		# Legend: name — $amount (pct%)
		legend_labels = []
		for label, val in zip(labels, values):
			pct = val / total * 100
			legend_labels.append(f'{label}  ${val:,.0f} ({pct:.0f}%)')

		ax.legend(
			wedges, legend_labels,
			loc='upper center',
			bbox_to_anchor=(0.5, -0.02),
			ncol=1,
			fontsize=11,
			frameon=False,
			handlelength=1.2,
			handleheight=1.2,
		)

		ax.set_title(title, fontsize=17, fontweight='bold', pad=16)
		fig.subplots_adjust(bottom=0.25)
		return _save(fig)

	@staticmethod
	def bar_chart(daily_data: List[Tuple[str, float]], title: str) -> Optional[io.BytesIO]:
		if not daily_data:
			return None

		plt.style.use('seaborn-v0_8-whitegrid')
		fig, ax = plt.subplots(figsize=(8, 6))

		dates = [d[0] for d in daily_data]
		amounts = [d[1] for d in daily_data]
		date_labels = [datetime.strptime(d, '%Y-%m-%d').strftime('%a\n%m/%d') for d in dates]

		max_amount = max(amounts) if amounts else 1
		colors = plt.cm.RdYlGn_r([a / max_amount for a in amounts])

		bars = ax.bar(range(len(dates)), amounts, color=colors,
					  edgecolor='white', linewidth=1.5, width=0.7)

		for bar, amount in zip(bars, amounts):
			height = bar.get_height()
			ax.annotate(
				f'${amount:.0f}',
				xy=(bar.get_x() + bar.get_width() / 2, height),
				xytext=(0, 4),
				textcoords="offset points",
				ha='center', va='bottom',
				fontsize=12, fontweight='bold',
			)

		ax.set_xticks(range(len(dates)))
		ax.set_xticklabels(date_labels, fontsize=11)
		ax.set_ylabel('Amount ($)', fontsize=13, fontweight='bold')
		ax.set_title(title, fontsize=17, fontweight='bold', pad=16)
		ax.tick_params(axis='y', labelsize=11)

		avg = sum(amounts) / len(amounts)
		total = sum(amounts)
		ax.axhline(y=avg, color='#E74C3C', linestyle='--', linewidth=2,
				   label=f'Avg: ${avg:,.2f}  \u2022  Total: ${total:,.2f}')
		ax.legend(loc='upper right', fontsize=11)

		plt.tight_layout()
		return _save(fig)

	@staticmethod
	def budget_chart(plan: Dict) -> Optional[io.BytesIO]:
		plt.style.use('seaborn-v0_8-whitegrid')

		all_categories = set(plan['planned_budgets'].keys()) | set(plan['actual_spending'].keys())
		categories = sorted(all_categories)

		fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 12),
										gridspec_kw={'height_ratios': [3, 2]})

		# --- Top: horizontal grouped bars (planned vs actual) ---
		if categories:
			short_names = [cat.split(' ', 1)[1][:12] if ' ' in cat else cat[:12]
						   for cat in categories]
			planned = [plan['planned_budgets'].get(cat, 0) for cat in categories]
			actual = [plan['actual_spending'].get(cat, 0) for cat in categories]

			y = np.arange(len(categories))
			height = 0.35

			ax1.barh(y + height / 2, planned, height, label='Planned',
					 color='#3498DB', alpha=0.85)
			ax1.barh(y - height / 2, actual, height, label='Actual',
					 color='#E74C3C', alpha=0.85)

			ax1.set_yticks(y)
			ax1.set_yticklabels(short_names, fontsize=12)
			ax1.set_xlabel('Amount ($)', fontsize=13, fontweight='bold')
			ax1.set_title('Budget vs Actual', fontsize=16, fontweight='bold', pad=12)
			ax1.legend(fontsize=12, loc='lower right')
			ax1.tick_params(axis='x', labelsize=11)
			ax1.grid(axis='x', alpha=0.3)
			ax1.invert_yaxis()

		# --- Bottom: donut showing overall budget status ---
		total_income = plan['total_actual_income'] or plan['total_projected_income'] or 1
		total_spent = plan['total_spent']
		remaining = max(0, total_income - total_spent)
		overspent = max(0, total_spent - total_income)

		if overspent > 0:
			sizes = [total_spent, overspent]
			labels = ['Spent', 'Overspent']
			donut_colors = ['#E74C3C', '#C0392B']
		else:
			sizes = [total_spent, remaining]
			labels = ['Spent', 'Remaining']
			donut_colors = ['#E74C3C', '#27AE60']

		pct_labels = [f'{l} ({s/sum(sizes)*100:.0f}%)' for l, s in zip(labels, sizes)]
		wedges, texts = ax2.pie(
			sizes,
			labels=pct_labels,
			colors=donut_colors,
			startangle=90,
			wedgeprops=dict(width=0.45, edgecolor='white', linewidth=2),
			textprops={'fontsize': 14, 'fontweight': 'bold'},
		)

		ax2.text(
			0, 0, f'${total_spent:,.0f}\nof\n${total_income:,.0f}',
			ha='center', va='center',
			fontsize=15, fontweight='bold', color='#2c3e50',
		)
		ax2.set_title('Overall Budget Status', fontsize=16, fontweight='bold', pad=12)

		plt.tight_layout(pad=2.0)
		return _save(fig)


__all__ = ["VisualizationService"]
