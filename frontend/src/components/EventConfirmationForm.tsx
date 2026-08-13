import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card } from "@/components/ui/card";
import { X, Check, Loader2, PartyPopper } from "lucide-react";

interface EventDetails {
  name: string;
  artist?: string | null;
  description?: string | null;
  event_date: string;
  venue: string;
  city: string;
  price?: number | null;
  ticket_url?: string | null;
}

interface EventConfirmationFormProps {
  eventDetails: EventDetails;
  onConfirm: (details: EventDetails) => Promise<void>;
  onCancel: () => void;
}

export const EventConfirmationForm = ({
  eventDetails,
  onConfirm,
  onCancel,
}: EventConfirmationFormProps) => {
  const [formData, setFormData] = useState<EventDetails>(eventDetails);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await onConfirm(formData);
      setIsSuccess(true);
    } catch (error) {
      setIsSubmitting(false);
    }
  };

  const formatDateForInput = (isoDate: string) => {
    try {
      const date = new Date(isoDate);
      return date.toISOString().slice(0, 16);
    } catch {
      return isoDate;
    }
  };

  // Success state
  if (isSuccess) {
    return (
      <Card className="p-8 border-cyan-500/30 bg-card text-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-16 h-16 rounded-full bg-cyan-500/20 flex items-center justify-center">
            <PartyPopper className="w-8 h-8 text-cyan-400" />
          </div>
          <h3 className="text-xl font-semibold font-montserrat text-cyan-400">
            Event Published!
          </h3>
          <p className="text-muted-foreground font-ibm-plex max-w-sm">
            <strong>{formData.name}</strong> at {formData.venue} in {formData.city} has been successfully added to laiive.
          </p>
          <Button
            onClick={onCancel}
            className="mt-4 bg-cyan-500 hover:bg-cyan-600 text-white"
            size="lg"
          >
            Add Another Event
          </Button>
        </div>
      </Card>
    );
  }

  const inputClassName = "font-ibm-plex focus-visible:ring-cyan-500 focus-visible:border-cyan-500";

  return (
    <Card className="p-6 border-cyan-500/30 bg-card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold font-montserrat text-cyan-400">Confirm Event Details</h3>
        <Button variant="ghost" size="icon" onClick={onCancel} disabled={isSubmitting}>
          <X className="w-4 h-4" />
        </Button>
      </div>

      <p className="text-sm text-muted-foreground mb-4 font-ibm-plex">
        Review and edit the extracted information before creating the event.
      </p>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="name">Event Name *</Label>
          <Input
            id="name"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            required
            disabled={isSubmitting}
            className={inputClassName}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="artist">Artist/Band *</Label>
          <Input
            id="artist"
            value={formData.artist || ""}
            onChange={(e) => setFormData({ ...formData, artist: e.target.value })}
            required
            disabled={isSubmitting}
            className={inputClassName}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="description">Description</Label>
          <Textarea
            id="description"
            value={formData.description || ""}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            disabled={isSubmitting}
            className="font-ibm-plex focus-visible:ring-cyan-500 focus-visible:border-cyan-500"
            rows={3}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="event_date">Date & Time *</Label>
          <Input
            id="event_date"
            type="datetime-local"
            value={formatDateForInput(formData.event_date)}
            onChange={(e) => setFormData({ ...formData, event_date: new Date(e.target.value).toISOString() })}
            required
            disabled={isSubmitting}
            className={inputClassName}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="venue">Venue *</Label>
          <Input
            id="venue"
            value={formData.venue}
            onChange={(e) => setFormData({ ...formData, venue: e.target.value })}
            required
            disabled={isSubmitting}
            className={inputClassName}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="city">City *</Label>
          <Input
            id="city"
            value={formData.city}
            onChange={(e) => setFormData({ ...formData, city: e.target.value })}
            required
            disabled={isSubmitting}
            className={inputClassName}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="price">Ticket Price</Label>
          <Input
            id="price"
            type="text"
            placeholder="Free or enter price"
            value={formData.price === 0 ? "Free" : (formData.price || "")}
            onChange={(e) => {
              const val = e.target.value.toLowerCase();
              if (val === "free" || val === "") {
                setFormData({ ...formData, price: 0 });
              } else {
                const num = parseFloat(e.target.value);
                setFormData({ ...formData, price: isNaN(num) ? null : num });
              }
            }}
            disabled={isSubmitting}
            className={inputClassName}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="ticket_url">Ticket URL</Label>
          <Input
            id="ticket_url"
            type="url"
            value={formData.ticket_url || ""}
            onChange={(e) => setFormData({ ...formData, ticket_url: e.target.value })}
            disabled={isSubmitting}
            className={inputClassName}
          />
        </div>

        <div className="flex gap-3 pt-4">
          <Button type="submit" className="flex-1 bg-cyan-500 hover:bg-cyan-600 text-white" size="lg" disabled={isSubmitting}>
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Publishing...
              </>
            ) : (
              <>
                <Check className="w-4 h-4 mr-2" />
                Confirm Event
              </>
            )}
          </Button>
          <Button type="button" variant="outline" onClick={onCancel} size="lg" disabled={isSubmitting} className="border-cyan-500/30 hover:bg-cyan-500/10">
            Cancel
          </Button>
        </div>
      </form>
    </Card>
  );
};
