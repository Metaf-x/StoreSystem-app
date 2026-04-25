export type UserRole = "customer" | "operator" | "admin";

export type CurrentUser = {
  id: string;
  name: string;
  email: string;
  role: UserRole;
};

export type LoginResponse = {
  user_id: string;
  message: string;
  access_token: string;
  token_type: string;
};

export type RefreshTokenResponse = {
  user_id: string | null;
  access_token: string | null;
};

export type Product = {
  product_id: string;
  user_id?: string;
  name: string;
  description: string | null;
  category: string | null;
  price: string | number;
  stock_quantity: number;
  supplier_id: string;
  is_available?: boolean;
  created_at?: string;
  updated_at?: string;
  image_url: string | null;
  weight: string | number | null;
  dimensions: string | null;
  manufacturer: string | null;
};

export type ProductPayload = {
  name: string;
  description: string | null;
  category: string | null;
  price: string;
  stock_quantity: number;
  supplier_id: string;
  image_url: string | null;
  weight: string | null;
  dimensions: string | null;
  manufacturer: string | null;
};

export type Supplier = {
  supplier_id: string;
  name: string;
};
