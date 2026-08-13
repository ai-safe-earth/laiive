import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Plus, MoreVertical, Building2, Music, Tent, Pencil, Trash2 } from "lucide-react";
import { EntityFormDialog, EntityType } from "./EntityFormDialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

interface Entity {
  id: string;
  name: string;
  type: EntityType;
  [key: string]: any;
}

interface EntityListProps {
  venues: any[];
  bands: any[];
  festivals: any[];
  onAddEntity: (type: EntityType, data: any) => Promise<void>;
  onUpdateEntity: (type: EntityType, id: string, data: any) => Promise<void>;
  onDeleteEntity: (type: EntityType, id: string) => Promise<void>;
  isLoading?: boolean;
}

const typeConfig = {
  venue: { icon: Building2, label: "Venue", color: "text-cyan-400 bg-cyan-500/20 border-cyan-500/30" },
  band: { icon: Music, label: "Band", color: "text-fuchsia-400 bg-fuchsia-500/20 border-fuchsia-500/30" },
  festival: { icon: Tent, label: "Festival", color: "text-yellow-400 bg-yellow-500/20 border-yellow-500/30" },
};

export const EntityList = ({
  venues,
  bands,
  festivals,
  onAddEntity,
  onUpdateEntity,
  onDeleteEntity,
  isLoading = false,
}: EntityListProps) => {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogType, setDialogType] = useState<EntityType>("venue");
  const [editingEntity, setEditingEntity] = useState<any>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [entityToDelete, setEntityToDelete] = useState<{ type: EntityType; id: string; name: string } | null>(null);
  const [addMenuOpen, setAddMenuOpen] = useState(false);

  // Combine all entities into a single list with type markers
  const allEntities: Entity[] = [
    ...venues.map((v) => ({ ...v, type: "venue" as EntityType })),
    ...bands.map((b) => ({ ...b, type: "band" as EntityType })),
    ...festivals.map((f) => ({ ...f, type: "festival" as EntityType })),
  ];

  const handleAdd = (type: EntityType) => {
    setDialogType(type);
    setEditingEntity(null);
    setDialogOpen(true);
    setAddMenuOpen(false);
  };

  const handleEdit = (entity: Entity) => {
    setDialogType(entity.type);
    setEditingEntity(entity);
    setDialogOpen(true);
  };

  const handleDeleteClick = (entity: Entity) => {
    setEntityToDelete({ type: entity.type, id: entity.id, name: entity.name });
    setDeleteDialogOpen(true);
  };

  const confirmDelete = async () => {
    if (entityToDelete) {
      await onDeleteEntity(entityToDelete.type, entityToDelete.id);
      setDeleteDialogOpen(false);
      setEntityToDelete(null);
    }
  };

  const handleSave = async (data: any) => {
    if (editingEntity) {
      await onUpdateEntity(dialogType, editingEntity.id, data);
    } else {
      await onAddEntity(dialogType, data);
    }
    setDialogOpen(false);
  };

  return (
    <Card className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="font-montserrat font-bold text-lg">Managed Entities</h2>
          <span className="text-xs px-2 py-0.5 bg-cyan-500/20 text-cyan-400 rounded-full border border-cyan-500/30">
            PRO
          </span>
        </div>
        <DropdownMenu open={addMenuOpen} onOpenChange={setAddMenuOpen}>
          <DropdownMenuTrigger asChild>
            <Button size="sm" variant="outline" className="gap-1">
              <Plus className="w-4 h-4" />
              Add
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="bg-card border-border">
            <DropdownMenuItem onClick={() => handleAdd("venue")} className="gap-2">
              <Building2 className="w-4 h-4 text-cyan-400" />
              Venue
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleAdd("band")} className="gap-2">
              <Music className="w-4 h-4 text-fuchsia-400" />
              Band
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleAdd("festival")} className="gap-2">
              <Tent className="w-4 h-4 text-yellow-400" />
              Festival
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {allEntities.length === 0 ? (
        <p className="text-sm text-muted-foreground text-center py-8">
          No entities added yet. Click "+ Add" to create your first venue, band, or festival.
        </p>
      ) : (
        <div className="space-y-2">
          {allEntities.map((entity) => {
            const config = typeConfig[entity.type];
            const Icon = config.icon;
            return (
              <div
                key={`${entity.type}-${entity.id}`}
                className="flex items-center justify-between p-3 rounded-lg bg-muted/50 border border-border/50 hover:border-border transition-colors"
              >
                <div className="flex items-center gap-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full border ${config.color} flex items-center gap-1`}>
                    <Icon className="w-3 h-3" />
                    {config.label}
                  </span>
                  <span className="font-medium">{entity.name}</span>
                </div>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                      <MoreVertical className="w-4 h-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="bg-card border-border">
                    <DropdownMenuItem onClick={() => handleEdit(entity)} className="gap-2">
                      <Pencil className="w-4 h-4" />
                      Edit
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => handleDeleteClick(entity)}
                      className="gap-2 text-destructive focus:text-destructive"
                    >
                      <Trash2 className="w-4 h-4" />
                      Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            );
          })}
        </div>
      )}

      <EntityFormDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        entityType={dialogType}
        entity={editingEntity}
        onSave={handleSave}
        isLoading={isLoading}
      />

      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent className="bg-card">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {entityToDelete?.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone. This will permanently delete this entity.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  );
};
