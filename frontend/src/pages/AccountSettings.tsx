import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { supabase } from "@/integrations/supabase/client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { ArrowLeft, Loader2 } from "lucide-react";
import { EntityList } from "@/components/entities/EntityList";
import { EntityType } from "@/components/entities/EntityFormDialog";

const industryRoles = [
  { value: 'promoter', label: 'Event Promoter' },
  { value: 'venue_manager', label: 'Venue Manager' },
  { value: 'artist_manager', label: 'Artist Manager' },
  { value: 'booking_agent', label: 'Booking Agent' },
  { value: 'musician', label: 'Musician / Band Member' },
  { value: 'other', label: 'Other' },
];

function getTableName(type: EntityType): string {
  return type === "venue" ? "venues" : type === "band" ? "bands" : "festivals";
}

const AccountSettings = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user, isLoading: authLoading, isPromoter } = useAuth();

  // Local form state
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [city, setCity] = useState("");
  const [country, setCountry] = useState("");
  const [industryRole, setIndustryRole] = useState("");

  // ─── Queries ────────────────────────────────────────────────

  const profileQuery = useQuery({
    queryKey: ["profile", user?.id],
    queryFn: async () => {
      const { data, error } = await supabase
        .from("profiles")
        .select("display_name")
        .eq("id", user!.id)
        .maybeSingle();
      if (error) throw error;
      return data;
    },
    enabled: !!user,
  });

  const promoterQuery = useQuery({
    queryKey: ["promoterProfile", user?.id],
    queryFn: async () => {
      const { data, error } = await supabase
        .from("promoter_profiles")
        .select("id, first_name, last_name, city, country, industry_role")
        .eq("user_id", user!.id)
        .maybeSingle();
      if (error) throw error;
      return data;
    },
    enabled: !!user && isPromoter,
  });

  const promoterProfileId = promoterQuery.data?.id ?? null;

  const entitiesQuery = useQuery({
    queryKey: ["entities", promoterProfileId],
    queryFn: async () => {
      const [venuesRes, bandsRes, festivalsRes] = await Promise.all([
        supabase.from("venues").select("*").eq("promoter_id", promoterProfileId!),
        supabase.from("bands").select("*").eq("promoter_id", promoterProfileId!),
        supabase.from("festivals").select("*").eq("promoter_id", promoterProfileId!),
      ]);
      if (venuesRes.error) throw venuesRes.error;
      if (bandsRes.error) throw bandsRes.error;
      if (festivalsRes.error) throw festivalsRes.error;
      return {
        venues: venuesRes.data ?? [],
        bands: bandsRes.data ?? [],
        festivals: festivalsRes.data ?? [],
      };
    },
    enabled: !!promoterProfileId,
  });

  // Sync query data → local form state
  useEffect(() => {
    if (user) setEmail(user.email || "");
  }, [user]);

  useEffect(() => {
    if (profileQuery.data) {
      setDisplayName(profileQuery.data.display_name || "");
    }
  }, [profileQuery.data]);

  useEffect(() => {
    if (promoterQuery.data) {
      setFirstName(promoterQuery.data.first_name || "");
      setLastName(promoterQuery.data.last_name || "");
      setCity(promoterQuery.data.city || "");
      setCountry(promoterQuery.data.country || "");
      setIndustryRole(promoterQuery.data.industry_role || "");
    }
  }, [promoterQuery.data]);

  // ─── Mutations ──────────────────────────────────────────────

  const saveMutation = useMutation({
    mutationFn: async () => {
      const { error: profileError } = await supabase
        .from("profiles")
        .update({ display_name: displayName.trim() })
        .eq("id", user!.id);
      if (profileError) throw profileError;

      if (isPromoter) {
        if (!firstName || !lastName || !city || !country || !industryRole) {
          throw new Error("Please fill in all professional information");
        }
        const { error: promoterError } = await supabase
          .from("promoter_profiles")
          .update({
            first_name: firstName.trim(),
            last_name: lastName.trim(),
            city: city.trim(),
            country: country.trim(),
            industry_role: industryRole,
          })
          .eq("user_id", user!.id);
        if (promoterError) throw promoterError;
      }
    },
    onSuccess: () => {
      toast.success("Profile updated successfully");
      queryClient.invalidateQueries({ queryKey: ["profile"] });
      queryClient.invalidateQueries({ queryKey: ["promoterProfile"] });
      navigate("/");
    },
    onError: (err: Error) => {
      toast.error(err.message || "Failed to update profile");
    },
  });

  const addEntityMutation = useMutation({
    mutationFn: async ({ type, data }: { type: EntityType; data: Record<string, unknown> }) => {
      const { error } = await supabase
        .from(getTableName(type))
        .insert({ ...data, promoter_id: promoterProfileId, created_by: user?.id });
      if (error) throw error;
    },
    onSuccess: (_data, { type }) => {
      toast.success(`${type.charAt(0).toUpperCase() + type.slice(1)} added`);
      queryClient.invalidateQueries({ queryKey: ["entities", promoterProfileId] });
    },
    onError: (_err, { type }) => toast.error(`Failed to add ${type}`),
  });

  const updateEntityMutation = useMutation({
    mutationFn: async ({ type, id, data }: { type: EntityType; id: string; data: Record<string, unknown> }) => {
      const { id: _id, type: _t, promoter_id: _p, created_at: _ca, updated_at: _ua, created_by: _cb, ...updateData } = data;
      const { error } = await supabase
        .from(getTableName(type))
        .update({ ...updateData, modified_by: user?.id })
        .eq("id", id);
      if (error) throw error;
    },
    onSuccess: (_data, { type }) => {
      toast.success(`${type.charAt(0).toUpperCase() + type.slice(1)} updated`);
      queryClient.invalidateQueries({ queryKey: ["entities", promoterProfileId] });
    },
    onError: (_err, { type }) => toast.error(`Failed to update ${type}`),
  });

  const deleteEntityMutation = useMutation({
    mutationFn: async ({ type, id }: { type: EntityType; id: string }) => {
      const { error } = await supabase.from(getTableName(type)).delete().eq("id", id);
      if (error) throw error;
    },
    onSuccess: (_data, { type }) => {
      toast.success(`${type.charAt(0).toUpperCase() + type.slice(1)} deleted`);
      queryClient.invalidateQueries({ queryKey: ["entities", promoterProfileId] });
    },
    onError: (_err, { type }) => toast.error(`Failed to delete ${type}`),
  });

  const isEntityLoading =
    addEntityMutation.isPending || updateEntityMutation.isPending || deleteEntityMutation.isPending;

  // ─── Handlers ───────────────────────────────────────────────

  const handleAddEntity = async (type: EntityType, data: Record<string, unknown>) => {
    await addEntityMutation.mutateAsync({ type, data });
  };

  const handleUpdateEntity = async (type: EntityType, id: string, data: Record<string, unknown>) => {
    await updateEntityMutation.mutateAsync({ type, id, data });
  };

  const handleDeleteEntity = async (type: EntityType, id: string) => {
    await deleteEntityMutation.mutateAsync({ type, id });
  };

  // ─── Render ─────────────────────────────────────────────────

  if (authLoading || profileQuery.isLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-card p-4">
        <div className="max-w-2xl mx-auto flex items-center gap-4">
          <button
            onClick={() => navigate("/")}
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <h1 className="font-montserrat font-bold text-lg">Account Settings</h1>
        </div>
      </header>

      <div className="max-w-2xl mx-auto px-4 py-8 space-y-6">
        <Card className="p-6 space-y-4">
          <h2 className="font-montserrat font-bold text-lg">Basic Information</h2>

          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" value={email} disabled className="bg-muted" />
            <p className="text-xs text-muted-foreground">Email cannot be changed</p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="displayName">Display Name</Label>
            <Input
              id="displayName"
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Enter your display name"
              maxLength={100}
            />
          </div>
        </Card>

        {isPromoter && (
          <>
            <Card className="p-6 space-y-4">
              <div className="flex items-center gap-2">
                <h2 className="font-montserrat font-bold text-lg">Professional Information</h2>
                <span className="text-xs px-2 py-0.5 bg-cyan-500/20 text-cyan-400 rounded-full border border-cyan-500/30">
                  PRO
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="firstName">First Name</Label>
                  <Input
                    id="firstName"
                    value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
                    placeholder="First name"
                    maxLength={50}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="lastName">Last Name</Label>
                  <Input
                    id="lastName"
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                    placeholder="Last name"
                    maxLength={50}
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="city">City</Label>
                  <Input
                    id="city"
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                    placeholder="Your city"
                    maxLength={100}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="country">Country</Label>
                  <Input
                    id="country"
                    value={country}
                    onChange={(e) => setCountry(e.target.value)}
                    placeholder="Your country"
                    maxLength={100}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="industryRole">Industry Role</Label>
                <Select value={industryRole} onValueChange={setIndustryRole}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select your role" />
                  </SelectTrigger>
                  <SelectContent>
                    {industryRoles.map((role) => (
                      <SelectItem key={role.value} value={role.value}>
                        {role.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </Card>

            <EntityList
              venues={entitiesQuery.data?.venues ?? []}
              bands={entitiesQuery.data?.bands ?? []}
              festivals={entitiesQuery.data?.festivals ?? []}
              onAddEntity={handleAddEntity}
              onUpdateEntity={handleUpdateEntity}
              onDeleteEntity={handleDeleteEntity}
              isLoading={isEntityLoading}
            />
          </>
        )}

        <Button
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending}
          className="w-full"
        >
          {saveMutation.isPending ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Saving...
            </>
          ) : (
            "Save Changes"
          )}
        </Button>
      </div>
    </div>
  );
};

export default AccountSettings;
