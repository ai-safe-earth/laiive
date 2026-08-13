import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Loader2 } from "lucide-react";

export type EntityType = "venue" | "band" | "festival";
export type EntityFormVariant = "default" | "pro";

interface EntityFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  entityType: EntityType;
  entity?: any;
  onSave: (data: any) => Promise<void>;
  isLoading?: boolean;
  variant?: EntityFormVariant;
}

export const EntityFormDialog = ({
  open,
  onOpenChange,
  entityType,
  entity,
  onSave,
  isLoading = false,
  variant = "default",
}: EntityFormDialogProps) => {
  const isPro = variant === "pro";
  const inputClassName = isPro
    ? "bg-background/50 border-cyan-500/30 focus:border-cyan-500 focus-visible:ring-cyan-500/30"
    : "";
  const buttonClassName = isPro
    ? "bg-cyan-500 hover:bg-cyan-600 text-black font-semibold"
    : "";
  const [formData, setFormData] = useState<any>({});

  useEffect(() => {
    if (entity) {
      setFormData(entity);
    } else {
      setFormData({});
    }
  }, [entity, open]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onSave(formData);
  };

  const updateField = (field: string, value: any) => {
    setFormData((prev: any) => ({ ...prev, [field]: value }));
  };

  const titles = {
    venue: entity ? "Edit Venue" : "Add Venue",
    band: entity ? "Edit Band" : "Add Band",
    festival: entity ? "Edit Festival" : "Add Festival",
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className={`max-w-lg max-h-[80vh] overflow-y-auto bg-card ${isPro ? "border-cyan-500/30" : ""}`}>
        <DialogHeader>
          <DialogTitle className="font-montserrat">{titles[entityType]}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Common name field */}
          <div className="space-y-2">
            <Label htmlFor="name">Name *</Label>
            <Input
              id="name"
              value={formData.name || ""}
              onChange={(e) => updateField("name", e.target.value)}
              placeholder={`${entityType.charAt(0).toUpperCase() + entityType.slice(1)} name`}
              required
              maxLength={200}
              className={inputClassName}
            />
          </div>

          {/* Venue specific fields */}
          {entityType === "venue" && (
            <>
              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  value={formData.description || ""}
                  onChange={(e) => updateField("description", e.target.value)}
                  placeholder="Describe the venue..."
                  maxLength={1000}
                  className={inputClassName}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="capacity">Capacity</Label>
                  <Input
                    id="capacity"
                    type="number"
                    value={formData.capacity || ""}
                    onChange={(e) => updateField("capacity", parseInt(e.target.value) || null)}
                    placeholder="e.g. 500"
                    className={inputClassName}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="atmosphere">Atmosphere</Label>
                  <Input
                    id="atmosphere"
                    value={formData.atmosphere || ""}
                    onChange={(e) => updateField("atmosphere", e.target.value)}
                    placeholder="e.g. Intimate, Underground"
                    maxLength={100}
                    className={inputClassName}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="address">Address</Label>
                <Input
                  id="address"
                  value={formData.address || ""}
                  onChange={(e) => updateField("address", e.target.value)}
                  placeholder="Street address"
                  maxLength={200}
                  className={inputClassName}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="city">City</Label>
                  <Input
                    id="city"
                    value={formData.city || ""}
                    onChange={(e) => updateField("city", e.target.value)}
                    placeholder="City"
                    maxLength={100}
                    className={inputClassName}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="country">Country</Label>
                  <Input
                    id="country"
                    value={formData.country || ""}
                    onChange={(e) => updateField("country", e.target.value)}
                    placeholder="e.g. Spain, Italy"
                    maxLength={100}
                    className={inputClassName}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="contact">Contact Email</Label>
                  <Input
                    id="contact"
                    type="email"
                    value={formData.contact || ""}
                    onChange={(e) => updateField("contact", e.target.value)}
                    placeholder="contact@venue.com"
                    maxLength={100}
                    className={inputClassName}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="phone">Phone</Label>
                  <Input
                    id="phone"
                    value={formData.phone || ""}
                    onChange={(e) => updateField("phone", e.target.value)}
                    placeholder="+34 123 456 789"
                    maxLength={30}
                    className={inputClassName}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="link">Website</Label>
                <Input
                  id="link"
                  type="url"
                  value={formData.link || ""}
                  onChange={(e) => updateField("link", e.target.value)}
                  placeholder="https://..."
                  maxLength={500}
                  className={inputClassName}
                />
              </div>
            </>
          )}

          {/* Band specific fields */}
          {entityType === "band" && (
            <>
              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  value={formData.description || ""}
                  onChange={(e) => updateField("description", e.target.value)}
                  placeholder="Describe the band..."
                  maxLength={1000}
                  className={inputClassName}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="members">Members</Label>
                <Textarea
                  id="members"
                  value={formData.members || ""}
                  onChange={(e) => updateField("members", e.target.value)}
                  placeholder="List band members..."
                  maxLength={500}
                  className={inputClassName}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="year_of_formation">Year of Formation</Label>
                  <Input
                    id="year_of_formation"
                    type="number"
                    value={formData.year_of_formation || ""}
                    onChange={(e) => updateField("year_of_formation", parseInt(e.target.value) || null)}
                    placeholder="e.g. 2015"
                    min={1900}
                    max={new Date().getFullYear()}
                    className={inputClassName}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="genre">Genre</Label>
                  <Input
                    id="genre"
                    value={formData.genre || ""}
                    onChange={(e) => updateField("genre", e.target.value)}
                    placeholder="e.g. Indie Rock, Jazz"
                    maxLength={100}
                    className={inputClassName}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="influences">Influences</Label>
                <Textarea
                  id="influences"
                  value={formData.influences || ""}
                  onChange={(e) => updateField("influences", e.target.value)}
                  placeholder="Musical influences..."
                  maxLength={500}
                  className={inputClassName}
                />
              </div>
            </>
          )}

          {/* Festival specific fields */}
          {entityType === "festival" && (
            <>
              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  value={formData.description || ""}
                  onChange={(e) => updateField("description", e.target.value)}
                  placeholder="Describe the festival..."
                  maxLength={1000}
                  className={inputClassName}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="first_edition">First Edition (Year)</Label>
                  <Input
                    id="first_edition"
                    type="number"
                    value={formData.first_edition || ""}
                    onChange={(e) => updateField("first_edition", parseInt(e.target.value) || null)}
                    placeholder="e.g. 2010"
                    min={1900}
                    max={new Date().getFullYear()}
                    className={inputClassName}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="genres">Genres</Label>
                  <Input
                    id="genres"
                    value={formData.genres || ""}
                    onChange={(e) => updateField("genres", e.target.value)}
                    placeholder="e.g. Electronic, House"
                    maxLength={200}
                    className={inputClassName}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="past_artists">Past Artists</Label>
                <Textarea
                  id="past_artists"
                  value={formData.past_artists || ""}
                  onChange={(e) => updateField("past_artists", e.target.value)}
                  placeholder="Artists who have performed..."
                  maxLength={1000}
                  className={inputClassName}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="address">Address</Label>
                <Input
                  id="address"
                  value={formData.address || ""}
                  onChange={(e) => updateField("address", e.target.value)}
                  placeholder="Festival address"
                  maxLength={200}
                  className={inputClassName}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="city">City</Label>
                  <Input
                    id="city"
                    value={formData.city || ""}
                    onChange={(e) => updateField("city", e.target.value)}
                    placeholder="City"
                    maxLength={100}
                    className={inputClassName}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="country">Country</Label>
                  <Input
                    id="country"
                    value={formData.country || ""}
                    onChange={(e) => updateField("country", e.target.value)}
                    placeholder="e.g. Spain, Italy"
                    maxLength={100}
                    className={inputClassName}
                  />
                </div>
              </div>
            </>
          )}

          <div className="flex gap-2 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              className={`flex-1 ${isPro ? "border-cyan-500/30 hover:border-cyan-500" : ""}`}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isLoading || !formData.name?.trim()}
              className={`flex-1 ${buttonClassName}`}
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Saving...
                </>
              ) : (
                "Save"
              )}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
};
