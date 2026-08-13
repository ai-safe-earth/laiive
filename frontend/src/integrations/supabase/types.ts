export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "13.0.5"
  }
  public: {
    Tables: {
      bands: {
        Row: {
          country: string | null
          created_at: string
          created_by: string | null
          description: string | null
          genre: string | null
          id: string
          influences: string | null
          members: string | null
          modified_by: string | null
          name: string
          promoter_id: string
          updated_at: string
          year_of_formation: number | null
        }
        Insert: {
          country?: string | null
          created_at?: string
          created_by?: string | null
          description?: string | null
          genre?: string | null
          id?: string
          influences?: string | null
          members?: string | null
          modified_by?: string | null
          name: string
          promoter_id: string
          updated_at?: string
          year_of_formation?: number | null
        }
        Update: {
          country?: string | null
          created_at?: string
          created_by?: string | null
          description?: string | null
          genre?: string | null
          id?: string
          influences?: string | null
          members?: string | null
          modified_by?: string | null
          name?: string
          promoter_id?: string
          updated_at?: string
          year_of_formation?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "bands_promoter_id_fkey"
            columns: ["promoter_id"]
            isOneToOne: false
            referencedRelation: "promoter_profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      conversations: {
        Row: {
          conversation_type: string
          created_at: string
          device_type: string | null
          id: string
          ip_address: string | null
          language: string | null
          message_content: string
          message_role: string
          session_id: string
          user_agent: string | null
        }
        Insert: {
          conversation_type: string
          created_at?: string
          device_type?: string | null
          id?: string
          ip_address?: string | null
          language?: string | null
          message_content: string
          message_role: string
          session_id: string
          user_agent?: string | null
        }
        Update: {
          conversation_type?: string
          created_at?: string
          device_type?: string | null
          id?: string
          ip_address?: string | null
          language?: string | null
          message_content?: string
          message_role?: string
          session_id?: string
          user_agent?: string | null
        }
        Relationships: []
      }
      events: {
        Row: {
          artist: string | null
          city: string
          created_at: string
          created_by: string | null
          description: string | null
          event_date: string
          id: string
          latitude: number | null
          longitude: number | null
          modified_by: string | null
          name: string
          price: number | null
          tags: string[] | null
          ticket_url: string | null
          updated_at: string
          venue: string
        }
        Insert: {
          artist?: string | null
          city: string
          created_at?: string
          created_by?: string | null
          description?: string | null
          event_date: string
          id?: string
          latitude?: number | null
          longitude?: number | null
          modified_by?: string | null
          name: string
          price?: number | null
          tags?: string[] | null
          ticket_url?: string | null
          updated_at?: string
          venue: string
        }
        Update: {
          artist?: string | null
          city?: string
          created_at?: string
          created_by?: string | null
          description?: string | null
          event_date?: string
          id?: string
          latitude?: number | null
          longitude?: number | null
          modified_by?: string | null
          name?: string
          price?: number | null
          tags?: string[] | null
          ticket_url?: string | null
          updated_at?: string
          venue?: string
        }
        Relationships: []
      }
      festivals: {
        Row: {
          address: string | null
          city: string | null
          country: string | null
          created_at: string
          created_by: string | null
          description: string | null
          first_edition: number | null
          genres: string | null
          id: string
          location: string | null
          modified_by: string | null
          name: string
          past_artists: string | null
          promoter_id: string
          updated_at: string
        }
        Insert: {
          address?: string | null
          city?: string | null
          country?: string | null
          created_at?: string
          created_by?: string | null
          description?: string | null
          first_edition?: number | null
          genres?: string | null
          id?: string
          location?: string | null
          modified_by?: string | null
          name: string
          past_artists?: string | null
          promoter_id: string
          updated_at?: string
        }
        Update: {
          address?: string | null
          city?: string | null
          country?: string | null
          created_at?: string
          created_by?: string | null
          description?: string | null
          first_edition?: number | null
          genres?: string | null
          id?: string
          location?: string | null
          modified_by?: string | null
          name?: string
          past_artists?: string | null
          promoter_id?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "festivals_promoter_id_fkey"
            columns: ["promoter_id"]
            isOneToOne: false
            referencedRelation: "promoter_profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      profiles: {
        Row: {
          avatar_url: string | null
          created_at: string
          display_name: string | null
          email: string | null
          id: string
          updated_at: string
        }
        Insert: {
          avatar_url?: string | null
          created_at?: string
          display_name?: string | null
          email?: string | null
          id: string
          updated_at?: string
        }
        Update: {
          avatar_url?: string | null
          created_at?: string
          display_name?: string | null
          email?: string | null
          id?: string
          updated_at?: string
        }
        Relationships: []
      }
      promoter_profiles: {
        Row: {
          city: string
          country: string | null
          created_at: string
          first_name: string
          id: string
          industry_role: string
          last_name: string
          updated_at: string
          user_id: string
        }
        Insert: {
          city: string
          country?: string | null
          created_at?: string
          first_name: string
          id?: string
          industry_role: string
          last_name: string
          updated_at?: string
          user_id: string
        }
        Update: {
          city?: string
          country?: string | null
          created_at?: string
          first_name?: string
          id?: string
          industry_role?: string
          last_name?: string
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
      user_query_usage: {
        Row: {
          created_at: string
          id: string
          query_count: number
          updated_at: string
          user_id: string
          week_start: string
        }
        Insert: {
          created_at?: string
          id?: string
          query_count?: number
          updated_at?: string
          user_id: string
          week_start: string
        }
        Update: {
          created_at?: string
          id?: string
          query_count?: number
          updated_at?: string
          user_id?: string
          week_start?: string
        }
        Relationships: []
      }
      user_roles: {
        Row: {
          created_at: string | null
          id: string
          role: Database["public"]["Enums"]["app_role"]
          user_id: string
        }
        Insert: {
          created_at?: string | null
          id?: string
          role: Database["public"]["Enums"]["app_role"]
          user_id: string
        }
        Update: {
          created_at?: string | null
          id?: string
          role?: Database["public"]["Enums"]["app_role"]
          user_id?: string
        }
        Relationships: []
      }
      venues: {
        Row: {
          address: string | null
          atmosphere: string | null
          capacity: number | null
          city: string | null
          contact: string | null
          country: string | null
          created_at: string
          created_by: string | null
          description: string | null
          id: string
          link: string | null
          location: string | null
          modified_by: string | null
          name: string
          phone: string | null
          promoter_id: string
          updated_at: string
        }
        Insert: {
          address?: string | null
          atmosphere?: string | null
          capacity?: number | null
          city?: string | null
          contact?: string | null
          country?: string | null
          created_at?: string
          created_by?: string | null
          description?: string | null
          id?: string
          link?: string | null
          location?: string | null
          modified_by?: string | null
          name: string
          phone?: string | null
          promoter_id: string
          updated_at?: string
        }
        Update: {
          address?: string | null
          atmosphere?: string | null
          capacity?: number | null
          city?: string | null
          contact?: string | null
          country?: string | null
          created_at?: string
          created_by?: string | null
          description?: string | null
          id?: string
          link?: string | null
          location?: string | null
          modified_by?: string | null
          name?: string
          phone?: string | null
          promoter_id?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "venues_promoter_id_fkey"
            columns: ["promoter_id"]
            isOneToOne: false
            referencedRelation: "promoter_profiles"
            referencedColumns: ["id"]
          },
        ]
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      has_role: {
        Args: {
          _role: Database["public"]["Enums"]["app_role"]
          _user_id: string
        }
        Returns: boolean
      }
    }
    Enums: {
      app_role: "admin" | "user" | "promoter"
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {
      app_role: ["admin", "user", "promoter"],
    },
  },
} as const
