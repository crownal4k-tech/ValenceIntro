package id.valence.intro;

import net.kyori.adventure.bossbar.BossBar;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import net.kyori.adventure.text.format.TextColor;
import net.kyori.adventure.text.format.TextDecoration;
import net.kyori.adventure.text.minimessage.MiniMessage;
import net.kyori.adventure.title.Title;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.World;
import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryCloseEvent;
import org.bukkit.event.inventory.InventoryDragEvent;
import org.bukkit.event.inventory.InventoryType;
import org.bukkit.event.player.PlayerDropItemEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.event.player.PlayerMoveEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.ItemFlag;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;
import org.bukkit.scheduler.BukkitRunnable;
import org.bukkit.scheduler.BukkitTask;

import java.time.Duration;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Intro Valence Roleplay (tema biru gradasi putih), dijalankan lewat command /intro.
 *
 * Alur: layar loading -> menu "Pilih Lokasi" -> teleport + title sambutan.
 *
 * Tampilan: dengan {@code custom-ui: true} plugin memakai resource pack di folder oraxen-pack
 * (font "valence:ui" + item model "valence:icon_*"). Dengan {@code custom-ui: false} plugin
 * jatuh ke tampilan teks/item vanilla, jadi tetap jalan tanpa pack.
 */
public final class ValenceIntro extends JavaPlugin implements Listener {

    // Menu 4 baris (36 slot). Posisi slot harus sama dengan gambar panel di pack.
    private static final int MENU_SIZE = 36;
    private static final int SLOT_LAST = 11;
    private static final int SLOT_CITY = 13;
    private static final int SLOT_OUTFIT = 15;
    private static final int SLOT_SPAWN = 31;

    private static final MiniMessage MM = MiniMessage.miniMessage();
    private static final TextColor BLUE = TextColor.fromHexString("#60a5fa");
    private static final String NS = "valence";

    private static final class Session {
        final BossBar bar;
        final boolean wasInvulnerable;
        BukkitTask task;
        Inventory menu;
        boolean finishing;
        boolean outfit;
        boolean useLast = true;

        Session(BossBar bar, boolean wasInvulnerable) {
            this.bar = bar;
            this.wasInvulnerable = wasInvulnerable;
        }
    }

    private final Map<UUID, Session> sessions = new HashMap<>();
    private NamespacedKey lastKey;

    @Override
    public void onEnable() {
        saveDefaultConfig();
        lastKey = new NamespacedKey(this, "last_location");
        getServer().getPluginManager().registerEvents(this, this);
    }

    @Override
    public void onDisable() {
        for (UUID id : new ArrayList<>(sessions.keySet())) {
            Player p = Bukkit.getPlayer(id);
            Session s = sessions.get(id);
            if (p != null && s != null) {
                p.closeInventory();
                cleanup(p, s);
            }
        }
    }

    // ------------------------------------------------------------------ teks dari config

    private boolean customUi() {
        return getConfig().getBoolean("custom-ui", true);
    }

    /**
     * Ambil teks MiniMessage dari config. Saat custom-ui mati, kunci "<nama>-text" dipakai
     * (versi teks biasa dari tampilan yang tadinya memakai gambar).
     */
    private Component ui(String key, String def) {
        String path = customUi() || !getConfig().contains(key + "-text") ? key : key + "-text";
        return msg(path, def);
    }

    private Component msg(String path, String def) {
        return MM.deserialize(getConfig().getString(path, def))
                .decoration(TextDecoration.ITALIC, false);
    }

    // ------------------------------------------------------------------ command

    @Override
    public boolean onCommand(CommandSender sender, Command cmd, String label, String[] args) {
        Player target;
        if (args.length > 0) {
            if (!sender.hasPermission("valenceintro.others")) {
                sender.sendMessage(Component.text("Kamu tidak punya izin.", NamedTextColor.RED));
                return true;
            }
            target = Bukkit.getPlayerExact(args[0]);
            if (target == null) {
                sender.sendMessage(Component.text("Pemain tidak ditemukan.", NamedTextColor.RED));
                return true;
            }
        } else if (sender instanceof Player p) {
            if (!p.hasPermission("valenceintro.use")) {
                p.sendMessage(Component.text("Kamu tidak punya izin.", NamedTextColor.RED));
                return true;
            }
            target = p;
        } else {
            sender.sendMessage("Pakai: /intro <player>");
            return true;
        }
        startIntro(target);
        return true;
    }

    // ------------------------------------------------------------------ fase 1: loading

    private void startIntro(Player p) {
        if (sessions.containsKey(p.getUniqueId())) return;

        int secs = Math.max(1, getConfig().getInt("loading-seconds", 4));
        BossBar bar = BossBar.bossBar(
                msg("loading-text", "<gradient:#2563eb:#ffffff>Memuat Valence...</gradient>"),
                0f, BossBar.Color.BLUE, BossBar.Overlay.PROGRESS);

        Session s = new Session(bar, p.isInvulnerable());
        sessions.put(p.getUniqueId(), s);

        p.setInvulnerable(true);
        // Layar hitam sampai pemain menekan SPAWN
        p.addPotionEffect(new PotionEffect(PotionEffectType.BLINDNESS,
                PotionEffect.INFINITE_DURATION, 0, false, false, false));
        p.showBossBar(bar);
        p.showTitle(Title.title(
                ui("title", "<bold><gradient:#1d4ed8:#60a5fa:#ffffff>VALENCE</gradient></bold>"),
                msg("subtitle", "<gradient:#93c5fd:#ffffff>ROLEPLAY</gradient>"),
                Title.Times.times(Duration.ZERO, Duration.ofSeconds(secs), Duration.ofMillis(300))));

        final int total = secs * 20;
        s.task = new BukkitRunnable() {
            int t = 0;

            @Override
            public void run() {
                if (!p.isOnline()) {
                    cancel();
                    return;
                }
                t += 2;
                bar.progress(Math.min(1f, (float) t / total));
                if (t >= total) {
                    cancel();
                    p.hideBossBar(bar);
                    openMenu(p, s);
                }
            }
        }.runTaskTimer(this, 0L, 2L);
    }

    // ------------------------------------------------------------------ fase 2: menu pilih lokasi

    private void openMenu(Player p, Session s) {
        s.menu = Bukkit.createInventory(null, MENU_SIZE,
                ui("menu-title", "<gradient:#2563eb:#bfdbfe>Pilih Lokasi</gradient>"));
        render(s);
        p.openInventory(s.menu);
    }

    private void render(Session s) {
        s.menu.clear();
        s.menu.setItem(SLOT_LAST, icon("icon_last", s.useLast, Material.CLOCK, "Lokasi Terakhir",
                "Muncul di tempat terakhir kamu keluar"));
        s.menu.setItem(SLOT_CITY, icon("icon_city", !s.useLast, Material.COMPASS, "Spawn Kota",
                "Muncul di spawn utama Valence"));
        s.menu.setItem(SLOT_OUTFIT, icon("icon_outfit", false, Material.LEATHER_CHESTPLATE, "Ganti Baju",
                "Buka menu pengganti skin / baju"));
        s.menu.setItem(SLOT_SPAWN, icon("icon_spawn", false, Material.AMETHYST_SHARD, "SPAWN",
                "Klik untuk masuk ke kota"));
    }

    /**
     * Satu tombol menu. Dengan custom-ui, ikonnya diambil dari item model di resource pack
     * ("valence:icon_x", dan "valence:icon_x_on" untuk yang sedang dipilih); kalau tidak,
     * item vanilla dengan kilau sebagai penanda pilihan.
     */
    private ItemStack icon(String model, boolean selected, Material fallback, String name, String lore) {
        boolean custom = customUi();
        ItemStack it = new ItemStack(custom ? Material.PAPER : fallback);
        ItemMeta meta = it.getItemMeta();

        if (custom) {
            meta.setItemModel(new NamespacedKey(NS, selected ? model + "_on" : model));
        } else {
            meta.setEnchantmentGlintOverride(selected);
        }

        meta.displayName(selected
                ? MM.deserialize("<bold><gradient:#3b82f6:#ffffff>" + name + "</gradient></bold>")
                        .decoration(TextDecoration.ITALIC, false)
                : Component.text(name, NamedTextColor.WHITE).decoration(TextDecoration.ITALIC, false));
        meta.lore(List.of(Component.text(lore, BLUE).decoration(TextDecoration.ITALIC, false)));
        meta.addItemFlags(ItemFlag.values());
        it.setItemMeta(meta);
        return it;
    }

    @EventHandler
    public void onClick(InventoryClickEvent e) {
        if (!(e.getWhoClicked() instanceof Player p)) return;
        Session s = sessions.get(p.getUniqueId());
        if (s == null || s.menu == null || e.getView().getTopInventory() != s.menu) return;
        e.setCancelled(true);
        if (e.getClickedInventory() != s.menu) return;

        switch (e.getRawSlot()) {
            case SLOT_LAST -> {
                s.useLast = true;
                render(s);
            }
            case SLOT_CITY -> {
                s.useLast = false;
                render(s);
            }
            case SLOT_OUTFIT -> openOutfit(p, s);
            case SLOT_SPAWN -> finish(p, s);
            default -> { }
        }
    }

    @EventHandler
    public void onDrag(InventoryDragEvent e) {
        if (!(e.getWhoClicked() instanceof Player p)) return;
        Session s = sessions.get(p.getUniqueId());
        if (s != null && s.menu != null && e.getView().getTopInventory() == s.menu) e.setCancelled(true);
    }

    /** Menu tidak bisa ditutup dengan ESC sebelum pemain menekan SPAWN. */
    @EventHandler
    public void onClose(InventoryCloseEvent e) {
        if (!(e.getPlayer() instanceof Player p)) return;
        Session s = sessions.get(p.getUniqueId());
        if (s == null || s.finishing || s.outfit || e.getInventory() != s.menu) return;
        Bukkit.getScheduler().runTask(this, () -> {
            if (p.isOnline() && sessions.get(p.getUniqueId()) == s && !s.finishing && !s.outfit) {
                p.openInventory(s.menu);
            }
        });
    }

    private void openOutfit(Player p, Session s) {
        s.outfit = true;
        p.closeInventory();
        String cmd = getConfig().getString("outfit-command", "");
        if (cmd != null && !cmd.isBlank()) p.performCommand(cmd);

        // Buka lagi menu lokasi setelah menu baju ditutup (atau setelah 5 menit).
        new BukkitRunnable() {
            int waited = 0;

            @Override
            public void run() {
                if (!p.isOnline() || sessions.get(p.getUniqueId()) != s || s.finishing) {
                    cancel();
                    return;
                }
                waited += 10;
                boolean nothingOpen = p.getOpenInventory().getType() == InventoryType.CRAFTING;
                if ((waited >= 20 && nothingOpen) || waited >= 6000) {
                    cancel();
                    s.outfit = false;
                    openMenu(p, s);
                }
            }
        }.runTaskTimer(this, 10L, 10L);
    }

    // ------------------------------------------------------------------ fase 3: spawn

    private void finish(Player p, Session s) {
        s.finishing = true;
        p.closeInventory();

        Location last = s.useLast ? readLast(p) : null;
        Location dest = last != null ? last : citySpawn();
        String label = last != null ? "Lokasi Terakhir" : "Spawn Kota";

        cleanup(p, s);
        p.teleport(dest);
        p.showTitle(Title.title(
                MM.deserialize("<bold><gradient:#2563eb:#ffffff>" + label + "</gradient></bold>"),
                msg("welcome-text", "<gradient:#93c5fd:#ffffff>Selamat datang di Valence Roleplay</gradient>"),
                Title.Times.times(Duration.ofMillis(500), Duration.ofSeconds(3), Duration.ofSeconds(1))));
    }

    private void cleanup(Player p, Session s) {
        if (s.task != null) s.task.cancel();
        p.hideBossBar(s.bar);
        p.removePotionEffect(PotionEffectType.BLINDNESS);
        p.setInvulnerable(s.wasInvulnerable);
        sessions.remove(p.getUniqueId());
    }

    // ------------------------------------------------------------------ lokasi

    private Location citySpawn() {
        var c = getConfig().getConfigurationSection("spawn");
        if (c != null) {
            World w = Bukkit.getWorld(c.getString("world", ""));
            if (w != null) {
                return new Location(w, c.getDouble("x"), c.getDouble("y"), c.getDouble("z"),
                        (float) c.getDouble("yaw"), (float) c.getDouble("pitch"));
            }
        }
        return Bukkit.getWorlds().get(0).getSpawnLocation();
    }

    private void saveLast(Player p) {
        Location l = p.getLocation();
        String v = String.join(";", l.getWorld().getName(),
                String.valueOf(l.getX()), String.valueOf(l.getY()), String.valueOf(l.getZ()),
                String.valueOf(l.getYaw()), String.valueOf(l.getPitch()));
        p.getPersistentDataContainer().set(lastKey, PersistentDataType.STRING, v);
    }

    private Location readLast(Player p) {
        String v = p.getPersistentDataContainer().get(lastKey, PersistentDataType.STRING);
        if (v == null) return null;
        try {
            String[] a = v.split(";");
            World w = Bukkit.getWorld(a[0]);
            if (w == null) return null;
            return new Location(w, Double.parseDouble(a[1]), Double.parseDouble(a[2]),
                    Double.parseDouble(a[3]), Float.parseFloat(a[4]), Float.parseFloat(a[5]));
        } catch (RuntimeException ex) {
            return null;
        }
    }

    // ------------------------------------------------------------------ pengaman selama intro

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        Player p = e.getPlayer();
        saveLast(p);
        Session s = sessions.get(p.getUniqueId());
        if (s != null) cleanup(p, s);
    }

    @EventHandler
    public void onMove(PlayerMoveEvent e) {
        if (!sessions.containsKey(e.getPlayer().getUniqueId()) || !e.hasChangedPosition()) return;
        Location to = e.getFrom().clone();
        to.setYaw(e.getTo().getYaw());
        to.setPitch(e.getTo().getPitch());
        e.setTo(to);
    }

    @EventHandler
    public void onInteract(PlayerInteractEvent e) {
        if (sessions.containsKey(e.getPlayer().getUniqueId())) e.setCancelled(true);
    }

    @EventHandler
    public void onDrop(PlayerDropItemEvent e) {
        if (sessions.containsKey(e.getPlayer().getUniqueId())) e.setCancelled(true);
    }
}
