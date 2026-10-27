export interface User {
  id: string;
  name: string;
  role: 'user' | 'repairman' | 'admin';
  userId?: string;
  dormRoom?: string;
  dormBuilding?: string;
  phone?: string;
  skills?: string;
  createdAt?: string;
  activeTasksCount?: number;
}

export interface RepairRequest {
  id: string;
  dormBuilding: string;
  dormFloor?: number | null;
  dormRoom: string;
  category: string;
  description: string;
  imageUrl?: string;
  status: 'waiting' | 'ready' | 'in_progress' | 'pending_evaluation' | 'closed' | 'rejected';
  priority: 'low' | 'normal' | 'high' | 'urgent';
  assignedTo?: string;
  adminNote?: string;
  workNote?: string;
  createdAt: string;
  updatedAt: string;
  userName?: string;
  userPhone?: string;
  assignedToName?: string;
  rating?: number;
  slaDueDate?: string;
  slaBreached?: number;
}

export interface Stats {
  totalRequests: number;
  pendingRequests: number;
  inProgressRequests: number;
  completedRequests: number;
  rejectedRequests: number;
  totalUsers: number;
  userCount: number;
  repairmanCount: number;
  categoryStats: { category: string; count: number }[];
  buildingStats?: { building: string; count: number }[];
  avgRating: string;
  reviewCount: number;
  trendData?: { date: string; count: number }[];
  slaComplianceRate?: number;
  averageResponseTimeHours?: number;
  totalCost?: number;
  partsConsumedStats?: { name: string; count: number; totalCost: number }[];
}

export interface Part {
  id: string;
  name: string;
  price: number;
  stock: number;
  createdAt: string;
}

export interface RepairPart {
  id: string;
  repairId: string;
  partId: string;
  quantity: number;
  price: number;
  partName?: string;
  createdAt: string;
}

export interface Notification {
  id: string;
  userId: string;
  title: string;
  message: string;
  type: string;
  relatedId?: string;
  isRead: number;
  createdAt: string;
}

export interface Announcement {
  id: string;
  title: string;
  content: string;
  authorId: string;
  createdAt: string;
  authorName?: string;
}

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
}

export interface PaginatedApiResponse<T> extends ApiResponse<T> {
  total: number;
  page?: number;
  pageSize?: number;
}
