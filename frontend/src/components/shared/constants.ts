import { translations } from '../../lib/i18n';

// ─── i18n Type-safe Helpers ──────────────────────────────────────────────────
export function tCat(cat: string, t: (key: keyof typeof translations.zh) => string): string {
  const key = `cat_${cat}` as keyof typeof translations.zh;
  if (key in translations.zh) {
    return t(key);
  }
  return CATEGORY_LABEL[cat] || cat;
}
export function tStatus(status: string, t: (key: keyof typeof translations.zh) => string): string {
  return t(`status_${status}` as keyof typeof translations.zh);
}
export function tPriority(priority: string, t: (key: keyof typeof translations.zh) => string): string {
  return t(`priority_${priority}` as keyof typeof translations.zh);
}

// ─── Status helpers ───────────────────────────────────────────────────────────
export const STATUS_LABEL: Record<string, string> = {
  waiting: '待接单', ready: '已接单', in_progress: '维修中',
  pending_evaluation: '待评价', closed: '已结案', rejected: '已拒绝',
};
export const DORM_BUILDING_GROUPS: { group: string; options: string[] }[] = [
  { group: '学生公寓', options: Array.from({ length: 10 }, (_, i) => `公寓${i + 1}栋`) },
  {
    group: '公共区域',
    options: [
      '启航楼（教学楼）', '远航楼（交流中心）', '领航楼（行政楼）',
      '思航轩', '护航轩', '训航轩（小平房）', '博航楼', '大国之翼',
      '文体馆', '食堂', '图书馆', '运营中心', '操场', '其他',
    ],
  },
];
export const DORM_BUILDINGS = DORM_BUILDING_GROUPS.flatMap((g) => g.options);
export const STATUS_COLOR: Record<string, string> = {
  waiting: 'bg-orange-100 text-orange-800',
  ready: 'bg-blue-100 text-blue-800',
  in_progress: 'bg-purple-100 text-purple-800',
  pending_evaluation: 'bg-yellow-100 text-yellow-800 ring-2 ring-yellow-300',
  closed: 'bg-gray-100 text-gray-800',
  rejected: 'bg-red-100 text-red-800',
};
export type FaultCategoryOption = { value: string; disabled?: boolean };
export const FAULT_CATEGORY_GROUPS: { group: string; options: FaultCategoryOption[] }[] = [
  {
    group: '综合类',
    options: [
      { value: 'lamp' }, { value: 'trip' }, { value: 'sink' }, { value: 'cistern' },
      { value: 'wardrobe' }, { value: 'bed' }, { value: 'desk' }, { value: 'lock' },
      { value: 'ceiling' }, { value: 'leak' }, { value: 'toilet_clog' },
      { value: 'cold_faucet' }, { value: 'cold_pipe' }, { value: 'floor_tile' },
      { value: 'wall' }, { value: 'door_frame' }, { value: 'glass_window' },
      { value: 'curtain' }, { value: 'screen_window' }, { value: 'drying_rack' },
      { value: 'outlet' }, { value: 'switch' },
    ],
  },
  {
    group: '热水类',
    options: [{ value: 'heat_pump' }, { value: 'shower' }],
  },
  {
    group: '家电类',
    options: [{ value: 'washer', disabled: true }, { value: 'ac' }],
  },
  {
    group: '其他类',
    options: [{ value: 'office' }, { value: 'other_item' }],
  },
];
export const CATEGORY_DISPLAY_GROUP: Record<string, 'general' | 'hotWater' | 'appliance' | 'other'> = {
  // 新版叶子故障分类
  lamp: 'general', trip: 'general', sink: 'general', cistern: 'general',
  wardrobe: 'general', bed: 'general', desk: 'general', lock: 'general',
  ceiling: 'general', leak: 'general', toilet_clog: 'general',
  cold_faucet: 'general', cold_pipe: 'general', floor_tile: 'general',
  wall: 'general', door_frame: 'general', glass_window: 'general',
  curtain: 'general', screen_window: 'general', drying_rack: 'general',
  outlet: 'general', switch: 'general',
  heat_pump: 'hotWater', shower: 'hotWater',
  washer: 'appliance', ac: 'appliance',
  office: 'other',
  other_item: 'other',
  // 历史大类工单的兼容映射
  water: 'hotWater', electricity: 'appliance', furniture: 'general',
  network: 'other', other: 'other',
};
export const CATEGORY_TO_SKILL: Record<string, string> = {
  sink: 'water', cistern: 'water', leak: 'water', toilet_clog: 'water',
  cold_faucet: 'water', cold_pipe: 'water', shower: 'water', heat_pump: 'water',
  lamp: 'electricity', trip: 'electricity', outlet: 'electricity', switch: 'electricity', ac: 'electricity',
  wardrobe: 'furniture', bed: 'furniture', desk: 'furniture', lock: 'furniture',
  ceiling: 'furniture', floor_tile: 'furniture', wall: 'furniture', door_frame: 'furniture',
  glass_window: 'furniture', curtain: 'furniture', screen_window: 'furniture', drying_rack: 'furniture',
  office: 'other',
  other_item: 'other',
};
export const REPAIRMAN_SKILL_OPTIONS = ['furniture', 'water', 'electricity', 'other'] as const;
export const CATEGORY_LABEL: Record<string, string> = {
  water: '热水类', electricity: '家电类', furniture: '综合类',
  other: '其他类',
};
export const PRIORITY_LABEL: Record<string, string> = {
  low: '低', normal: '普通', high: '高', urgent: '紧急',
};
export const PRIORITY_COLOR: Record<string, string> = {
  low: 'bg-gray-100 text-gray-700',
  normal: 'bg-blue-50 text-blue-700',
  high: 'bg-orange-100 text-orange-700',
  urgent: 'bg-red-100 text-red-700',
};
