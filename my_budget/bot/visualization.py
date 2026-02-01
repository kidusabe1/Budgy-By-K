"""Visualization utilities for charts."""

import io
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import matplotlib

matplotlib.use('Agg')  # Non-interactive backend for servers
import matplotlib.pyplot as plt
import numpy as np


class VisualizationService:
	"""Creates charts for summaries."""

	@staticmethod
	def pie_chart(data: Dict[str, float], title: str) -> Optional[io.BytesIO]:
		if not data:
			return None

		plt.style.use('seaborn-v0_8-whitegrid')
		fig, ax = plt.subplots(figsize=(10, 8))

		labels = [cat.split(' ', 1)[1] if ' ' in cat else cat for cat in data.keys()]
		values = list(data.values())

		colors = [
			'#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
			'#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9', '#F8B500',
		]

		explode = [0.02] * len(values)
		wedges, texts, autotexts = ax.pie(
			values,
			labels=labels,
			autopct='%1.1f%%',
			colors=colors[:len(values)],
			explode=explode,
			shadow=True,
			startangle=90,
			textprops={'fontsize': 11, 'fontweight': 'bold'},
		)

		for autotext in autotexts:
			autotext.set_color('white')
			autotext.set_fontsize(10)

		ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
		total = sum(values)
		ax.annotate(
			f'Total: ${total:.2f}',
			xy=(0, 0),
			fontsize=14,
			ha='center',
			va='center',
			fontweight='bold',
			bbox=dict(boxstyle='round', facecolor='white', alpha=0.8),
		)

		plt.tight_layout()
		buf = io.BytesIO()
		plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white', edgecolor='none')
		buf.seek(0)
		plt.close(fig)
		return buf

	@staticmethod
	def bar_chart(daily_data: List[Tuple[str, float]], title: str) -> Optional[io.BytesIO]:
		if not daily_data:
			return None

		plt.style.use('seaborn-v0_8-whitegrid')
		fig, ax = plt.subplots(figsize=(12, 6))

		dates = [d[0] for d in daily_data]
		amounts = [d[1] for d in daily_data]
		date_labels = [datetime.strptime(d, '%Y-%m-%d').strftime('%a\n%m/%d') for d in dates]

		max_amount = max(amounts) if amounts else 1
		colors = plt.cm.RdYlGn_r([a / max_amount for a in amounts])

		bars = ax.bar(range(len(dates)), amounts, color=colors, edgecolor='white', linewidth=1.5)
		for bar, amount in zip(bars, amounts):
			height = bar.get_height()
			ax.annotate(
				f'${amount:.0f}',
				xy=(bar.get_x() + bar.get_width() / 2, height),
				xytext=(0, 3),
				textcoords="offset points",
				ha='center',
				va='bottom',
				fontsize=10,
				fontweight='bold',
			)

		ax.set_xticks(range(len(dates)))
		ax.set_xticklabels(date_labels, fontsize=10)
		ax.set_ylabel('Amount ($)', fontsize=12, fontweight='bold')
		ax.set_title(title, fontsize=16, fontweight='bold', pad=20)

		avg = sum(amounts) / len(amounts)
		ax.axhline(y=avg, color='#E74C3C', linestyle='--', linewidth=2, label=f'Avg: ${avg:.2f}')
		ax.legend(loc='upper right')

		total = sum(amounts)
		ax.annotate(
			f'Total: ${total:.2f}',
			xy=(0.98, 0.98),
			xycoords='axes fraction',
			fontsize=12,
			ha='right',
			va='top',
			fontweight='bold',
			bbox=dict(boxstyle='round', facecolor='#3498DB', alpha=0.8, edgecolor='none'),
			color='white',
		)

		plt.tight_layout()
		buf = io.BytesIO()
		plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white', edgecolor='none')
		buf.seek(0)
		plt.close(fig)
		return buf

	@staticmethod
	def budget_chart(plan: Dict) -> Optional[io.BytesIO]:
		plt.style.use('seaborn-v0_8-whitegrid')
		fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

		all_categories = set(plan['planned_budgets'].keys()) | set(plan['actual_spending'].keys())
		categories = sorted(all_categories)

		if categories:
			short_names = [cat.split(' ', 1)[1][:10] if ' ' in cat else cat[:10] for cat in categories]
			planned = [plan['planned_budgets'].get(cat, 0) for cat in categories]
			actual = [plan['actual_spending'].get(cat, 0) for cat in categories]

			x = np.arange(len(categories))
			width = 0.35

			ax1.bar(x - width / 2, planned, width, label='Planned', color='#3498DB', alpha=0.8)
			ax1.bar(x + width / 2, actual, width, label='Actual', color='#E74C3C', alpha=0.8)

			ax1.set_xlabel('Category', fontsize=11)
			ax1.set_ylabel('Amount ($)', fontsize=11)
			ax1.set_title('Budget vs Actual by Category', fontsize=14, fontweight='bold')
			ax1.set_xticks(x)
			ax1.set_xticklabels(short_names, rotation=45, ha='right', fontsize=9)
			ax1.legend()
			ax1.grid(axis='y', alpha=0.3)

		total_income = plan['total_actual_income'] or plan['total_projected_income'] or 1
		total_spent = plan['total_spent']
		remaining = max(0, total_income - total_spent)
		overspent = max(0, total_spent - total_income)

		if overspent > 0:
			sizes = [total_spent, overspent]
			labels = ['Spent', 'Overspent']
			colors = ['#E74C3C', '#C0392B']
		else:
			sizes = [total_spent, remaining]
			labels = ['Spent', 'Remaining']
			colors = ['#E74C3C', '#27AE60']

		ax2.pie(
			sizes,
			labels=labels,
			autopct='%1.1f%%',
			colors=colors,
			startangle=90,
			wedgeprops=dict(width=0.5),
		)
		ax2.annotate(
			f'${total_spent:.0f}\nof\n${total_income:.0f}',
			xy=(0, 0),
			fontsize=14,
			ha='center',
			va='center',
			fontweight='bold',
		)
		ax2.set_title('Overall Budget Status', fontsize=14, fontweight='bold')

		plt.tight_layout()
		buf = io.BytesIO()
		plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white', edgecolor='none')
		buf.seek(0)
		plt.close(fig)
		return buf


__all__ = ["VisualizationService"]
