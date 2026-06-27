from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from core.models import Board, User, Thread, Post, ActivityTier
import random
import datetime

BOARDS = [
    ('tech',     'Technology & Privacy', '💻', False),
    ('cooking',  'Cooking & Food',       '🍳', False),
    ('gaming',   'Gaming',               '🎮', False),
    ('music',    'Music',                '🎵', False),
    ('diy',      'DIY & Repair',         '🔧', False),
    ('fitness',  'Fitness',              '💪', False),
    ('film',     'Film & TV',            '🎬', False),
    ('outdoors', 'Outdoors & Nature',    '🏕️', False),
    ('animals',  'Animals',              '🐾', False),
    ('current',  'Current Affairs',      '📰', False),
    ('random',   'Random',               '🎲', True),
]

TECH_TITLES = [
    "Anyone else notice RAM prices dropping again?",
    "Best terminal emulator right now — settle this",
    "Rust is genuinely replacing C in my workflow",
    "What's your homelab running right now?",
    "Django vs FastAPI for a greenfield project",
    "Is ARM the future of desktop?",
    "Vim or Neovim — does it even matter anymore",
    "My SSD died and I lost everything. Backup your stuff.",
    "Linux on the desktop is finally just... fine",
    "VPN providers — who do you actually trust?",
    "Tor browser for daily use — practical or paranoid?",
    "Self-hosting everything: what's actually worth it",
    "Signal vs Session vs Matrix — threat model matters",
    "Privacy-respecting search engines compared",
    "What data does your ISP actually see?",
    "Running your own DNS — is it worth the hassle",
    "De-googling in 2025 — what's your stack",
    "Open source alternatives that are actually better",
    "End-to-end encryption explained without the jargon",
    "Passkeys — finally ready to replace passwords?",
    "Mechanical keyboard thread — what are you typing on",
    "What's your backup strategy and why is it wrong",
    "Browser fingerprinting is scarier than cookies",
    "Best single-board computer for a home server",
    "Ad blocking in 2025 — uBlock is still king",
]
COOKING_TITLES = [
    "Sourdough starter tips — mine keeps dying",
    "What's the cheapest cut of meat that tastes expensive?",
    "Finally nailed a proper ramen broth after 6 attempts",
    "Cast iron vs carbon steel — which do you cook on?",
    "Fermentation general — kimchi, koji, miso",
    "Why does restaurant pasta taste better than mine",
    "Pressure cooker changed my life, no exaggeration",
    "Best knife under £50 — opinions",
    "Homemade hot sauce thread",
    "I've eaten the same meal prep for 3 years and I'm fine",
    "Stock from scratch vs carton — is it worth it",
    "Bread baking — what went wrong this week",
    "One pan meals that don't feel like a punishment",
    "What's your go-to dish when you're exhausted",
    "Spice rack recommendations — what do you actually use",
    "Eggs — the most underrated ingredient",
    "Slow cooker recipes that actually work",
    "Cooking for one without wasting half the ingredients",
    "Regional food you grew up with that nobody else knows",
    "What cookbook actually taught you something",
    "Proper chips at home — achievable or not",
    "Batch cooking Sunday thread",
    "Cheap protein sources that don't taste like cardboard",
    "Umami — what it is and how to add it",
    "Best thing you've cooked this month",
]
GAMING_TITLES = [
    "What game has the best modding community?",
    "Is the 4090 even worth it at 1440p?",
    "Games that made you feel genuinely lonely",
    "Recommend me something I've never heard of",
    "Why do AAA games keep shipping broken",
    "The golden age of gaming was whenever you were 14",
    "Couch co-op is a dying genre and it hurts",
    "My GPU died mid-raid. Tell me it gets better.",
    "Roguelikes — what are you currently dying in",
    "Games with genuinely good writing",
    "Emulation in 2025 — what's your setup",
    "What game do you return to every year",
    "Indie games that punched above their weight",
    "What genre did you write off and then get into",
    "Most immersive game world you've experienced",
    "Fighting games — approachable or deliberately obtuse",
    "Gaming on Linux — where are we now",
    "What game has the best soundtrack",
    "Open world fatigue — is it just me",
    "Multiplayer games with good communities",
    "Games that respect your time",
    "What are you playing this weekend",
    "Most disappointing sequel you waited years for",
    "Hidden gem thread — post something obscure",
    "Controller or keyboard — context dependent?",
]
MUSIC_TITLES = [
    "What are you listening to right now",
    "Albums that took 10 listens to click",
    "Vinyl revival — genuine or nostalgia",
    "Headphones under £100 worth buying",
    "Genre you grew up dismissing and now love",
    "Live music experiences that stayed with you",
    "Music production on a budget — where to start",
    "Albums with no skips — name yours",
    "What does music mean to you when words fail",
    "Discovering old artists — what led you there",
    "Streaming killed the album format. Discuss.",
    "Instruments you wish you'd learned earlier",
    "Music that soundtracks specific memories",
    "Deep cuts from artists everyone knows",
    "What's the last gig you went to",
    "Recommend something from a genre I'd never pick",
    "Music theory — useful or does it kill creativity",
    "Artists doing genuinely interesting things right now",
    "The loudness war and whether it matters",
    "Playlists for specific moods — share yours",
    "Best album covers — does artwork still matter",
    "Music you're embarrassed to love but don't stop playing",
    "Folk music appreciation thread",
    "Electronic music gateway albums",
    "What did you listen to obsessively at 16",
]
DIY_TITLES = [
    "First time tiling — tips before I make a mess",
    "Recommend a decent drill that won't die in a year",
    "Plaster repair — what am I doing wrong",
    "Rewiring a lamp, how hard can it be",
    "Woodworking for complete beginners — where to start",
    "What's in your toolkit that you couldn't work without",
    "Fixing a dripping tap — step by step",
    "Insulating a loft properly — worth the effort",
    "3D printing for home repairs — what have you made",
    "When to DIY and when to just pay someone",
    "Painting walls without it looking amateur",
    "Sanding floors — hired or rented the machine?",
    "Workshop setup on a budget",
    "Fixing furniture instead of replacing it",
    "What YouTube channels actually taught you something",
    "Plumbing I can do myself vs plumbing I shouldn't touch",
    "Best investment I made for the home was...",
    "Cable management that doesn't look awful",
    "Weatherproofing windows before winter",
    "Garden shed build — lessons learned",
    "Fixing squeaky floorboards properly",
    "What tool do you wish you'd bought sooner",
    "Tiling grout choices — more important than you think",
    "Damp problems — diagnosis before treatment",
    "Show me something you fixed instead of replacing",
]
FITNESS_TITLES = [
    "Gym vs home setup — where did you land",
    "What actually made you consistent",
    "Running in winter — how do you motivate",
    "Nutrition basics without the bro science",
    "Injury that set you back and how you came back",
    "Bodyweight training — underrated or limited",
    "What fitness goal surprised you when you hit it",
    "Sleep is the most underrated recovery tool",
    "Walking — seriously underestimated",
    "Cycling for fitness — road, MTB, or just commuting",
    "What changed when you started tracking properly",
    "Strength training programming for beginners",
    "Mental health benefits of exercise — your experience",
    "Gym anxiety — does it go away",
    "What does your morning routine look like",
    "Swimming as the complete exercise",
    "Protein — how much do you actually need",
    "Rest days — how to take them without guilt",
    "Martial arts for fitness and discipline",
    "What kept you going when you wanted to quit",
    "Cheap ways to stay fit without a gym",
    "HIIT vs steady state — context dependent",
    "Flexibility and mobility — why I ignored it too long",
    "Fitness after 40 — what changes",
    "Show me your progress — before and after thread",
]
FILM_TITLES = [
    "Films that genuinely changed how you see things",
    "Sequels better than the original",
    "What are you watching this weekend",
    "Cinematography that stopped you mid-scene",
    "Documentaries that felt like fiction",
    "Most rewatchable film you own",
    "TV series that maintained quality start to finish",
    "Directors whose entire filmography is worth it",
    "Films that bombed but deserved better",
    "Endings that actually landed",
    "Streaming has too much content — how do you choose",
    "Foreign language films that hit differently",
    "Practical effects vs CGI — does it matter",
    "What film do you recommend to everyone",
    "Guilty pleasure films you'll defend",
    "Horror that genuinely unsettled you",
    "Films with perfect soundtracks",
    "Adaptations better than the source material",
    "What TV show do you wish had one more season",
    "Slow cinema — do you have patience for it",
    "Animated films that aren't just for children",
    "What decade had the best films",
    "Film you walked out of and then finished later",
    "Underrated actors who deserve more",
    "What are you watching with subtitles right now",
]
OUTDOORS_TITLES = [
    "Best hike you've done this year",
    "Wild camping — where and how",
    "Navigation without a phone — is it a lost skill",
    "Kit you carry every time without question",
    "Weather caught you out — what happened",
    "Favourite wild swimming spots",
    "Foraging basics — what's safe to start with",
    "Birdwatching thread — what have you spotted",
    "Mountain biking trails worth travelling to",
    "Solo walking — how do you plan for safety",
    "Lightweight camping — what did you cut",
    "Coastal walking routes that stayed with you",
    "What got you outdoors in the first place",
    "Winter hiking — gear and mindset",
    "Hammock camping vs tent — which camp are you in",
    "Urban nature — parks and green spaces that surprised you",
    "Photography outdoors — tips for not ruining the moment",
    "Trail running — entry point for a complete beginner",
    "Responsible wild camping — leave no trace in practice",
    "What's in your day pack",
    "Stargazing locations with low light pollution",
    "Kayaking and canoeing — where to start",
    "Favourite season to be outside and why",
    "Landscape that made you stop and just look",
    "Recommended reads on the outdoors",
]
ANIMALS_TITLES = [
    "What are your pets up to right now",
    "Wildlife you spotted this week",
    "Dog training — what actually works",
    "Cat behaviour that still baffles you",
    "Garden birds — how to attract more",
    "Rescue animals — your story",
    "Keeping chickens — is it worth it",
    "Fish keeping for beginners — what I wish I'd known",
    "Exotic pets — the reality vs the idea",
    "Vet bills — how do you manage it",
    "Animals that surprised you with their intelligence",
    "Wildlife conservation — what can individuals actually do",
    "Introducing a new pet to an existing one",
    "Losing a pet — sharing and support",
    "Hedgehogs in the garden — helping them survive",
    "Insects and their underrated importance",
    "What animal could you talk about for hours",
    "Rewilding — do you follow any projects",
    "Photographing wildlife — patience and kit",
    "Strange animal behaviour you've witnessed",
    "Urban foxes — nuisance or fascinating",
    "What animal changed how you think about something",
    "Marine life that genuinely astonishes you",
    "Working animals — dogs, horses, birds of prey",
    "Best nature documentary you've seen",
]
CURRENT_TITLES = [
    "What story are you actually following right now",
    "Media bias — how do you compensate for it",
    "Local news matters more than national. Discuss.",
    "Technology policy nobody seems to be reading properly",
    "Privacy legislation — is any of it working",
    "What did you change your mind about this year",
    "Journalism that held power to account recently",
    "Economic news explained without the spin",
    "Stories being ignored that shouldn't be",
    "Online censorship — where is the line",
    "Platform power and what to do about it",
    "Things that seemed fringe that went mainstream",
    "Freedom of speech vs freedom from harm — still unresolved",
    "What are you reading for actual news",
    "The gap between what's reported and what's happening",
    "Environmental news without the doom or the denial",
    "What policy would you actually implement if you could",
    "Regulation of AI — too fast, too slow, or wrong focus",
    "Local government — ignored until it affects you",
    "Protest and civil disobedience — when is it justified",
    "Historical parallels people are drawing — valid or not",
    "Corporate power and accountability",
    "What does free speech actually require",
    "Misinformation — how do you evaluate sources",
    "What gives you cautious optimism right now",
]
RANDOM_TITLES = [
    "What skill did you pick up that actually stuck",
    "Unpopular opinion — go",
    "Things that aged badly: a thread",
    "What's the best money you've ever spent",
    "Shower thoughts that genuinely troubled you",
    "Describe your job badly",
    "What would you do with a completely free week",
    "Rate your month 1-10 and explain",
    "Something you're proud of that nobody knows about",
    "What do you do when you can't sleep",
    "Books that changed something for you",
    "Hobbies you picked up and actually kept",
    "What advice do you wish someone had given you",
    "Places you've been that stayed with you",
    "What's something you make from scratch that others buy",
    "Habits that took years to build but are now automatic",
    "What are you learning right now",
    "Something mundane you find genuinely satisfying",
    "Favourite walk you take regularly",
    "What does a good day look like for you",
    "Things you believed that turned out to be wrong",
    "Best conversation you've had recently",
    "What would you tell your 20-year-old self",
    "Something small that made this week better",
    "What are you looking forward to",
]

REPLIES = [
    "Agreed, this has been my experience too.",
    "Completely wrong, here's why: ...",
    "Same thing happened to me last month.",
    "Can you share more details about your setup?",
    "This is the way.",
    "Has anyone tried the alternative approach?",
    "Lurker here, finally posting. Good thread.",
    "I've been doing this for years and never knew that.",
    "Counterpoint: it depends entirely on your use case.",
    "Bookmarking this for later.",
    "The real answer is somewhere in the middle.",
    "Interesting, what's your source on that?",
    "OP is based.",
    "Touch grass my friend.",
    "This thread delivered.",
    "Why does nobody talk about the obvious solution here",
    "Third option nobody is mentioning: just don't",
    "Works on my machine.",
    "Skill issue.",
    "Based and redpilled." ,
    "Finally someone said it.",
    "This comment section is exactly why I love this site.",
    "I tested this last week, results were mixed.",
    "Downvoting because wrong but also upvoting because funny.",
    "The documentation literally says otherwise...",
]

TITLE_MAP = {
    'tech':     TECH_TITLES,
    'cooking':  COOKING_TITLES,
    'gaming':   GAMING_TITLES,
    'music':    MUSIC_TITLES,
    'diy':      DIY_TITLES,
    'fitness':  FITNESS_TITLES,
    'film':     FILM_TITLES,
    'outdoors': OUTDOORS_TITLES,
    'animals':  ANIMALS_TITLES,
    'current':  CURRENT_TITLES,
    'random':   RANDOM_TITLES,
}


class Command(BaseCommand):
    help = 'Seed boards + 25 threads each with realistic reply counts'

    def add_arguments(self, parser):
        parser.add_argument('--threads', type=int, default=25)
        parser.add_argument('--max-replies', type=int, default=40)

    @transaction.atomic
    def handle(self, *args, **options):
        n_threads = options['threads']
        max_replies = options['max_replies']

        # Always ensure boards exist
        for slug, name, icon, nsfw in BOARDS:
            Board.objects.get_or_create(slug=slug, defaults={'name': name, 'icon': icon, 'nsfw': nsfw})
        self.stdout.write(self.style.SUCCESS(f'✓ {len(BOARDS)} boards'))

        # Skip thread/post seeding if data already exists — safe to run on every restart
        if Thread.objects.exists():
            self.stdout.write('  Threads already present — skipping seed. Run with --force to reseed.')
            return

        # Default activity tiers — only create if none exist so operator
        # customisations aren't overwritten on restart
        if not ActivityTier.objects.exists():
            default_tiers = [
                ('Lurker',          0,    0),
                ('Regular',         10,   1),
                ('Veteran',         100,  2),
                ('Prolific Poster', 500,  3),
                ('Legend',          2000, 4),
            ]
            ActivityTier.objects.bulk_create([
                ActivityTier(label=label, min_posts=min_posts, order=order)
                for label, min_posts, order in default_tiers
            ])
            self.stdout.write(self.style.SUCCESS('✓ Default activity tiers created'))
        else:
            self.stdout.write('  Activity tiers already exist, skipping')

        # Seed user
        anon, _ = User.objects.get_or_create(username='anon', defaults={'post_count': 0})
        if _:
            anon.set_password('anon1234')
            anon.display_name = 'anon'
            anon.save()

        # Create a handful of usernames for variety
        usernames = ['anon', 'throwaway', 'lurker99', 'op_here', 'sage', 'based_user', 'newfag', 'oldfag']
        users = [anon]
        for name in usernames[1:]:
            u, created = User.objects.get_or_create(username=name)
            if created:
                u.set_password('password')
                u.display_name = name
                u.save()
            users.append(u)

        boards = Board.objects.all()
        total_threads = 0
        total_posts = 0

        for board in boards:
            titles = TITLE_MAP.get(board.slug, [])
            # Cycle through titles to fill 25 threads
            thread_titles = []
            while len(thread_titles) < n_threads:
                thread_titles.extend(titles)
            thread_titles = thread_titles[:n_threads]

            for i, title in enumerate(thread_titles):
                # Stagger creation times over past 30 days
                created = timezone.now() - datetime.timedelta(
                    days=random.randint(1, 30),  # minimum 1 day ago
                    hours=random.randint(0, 23),
                    minutes=random.randint(0, 59),
                )
                thread = Thread.objects.create(
                    board=board,
                    author=random.choice(users),
                    title=f"{title} [{i+1}]" if i >= len(titles) else title,
                    body=f"Opening post for thread: {title}. Let's discuss.",
                    last_reply_at=created,
                    created_at=created,
                )

                # Random reply count (weighted toward lower numbers)
                n_replies = random.choices(
                    range(0, max_replies + 1),
                    weights=[max(1, max_replies - r) for r in range(max_replies + 1)]
                )[0]

                last_reply_at = created
                for p in range(n_replies):
                    reply_time = last_reply_at + datetime.timedelta(minutes=random.randint(2, 120))
                    Post.objects.create(
                        thread=thread,
                        author=random.choice(users),
                        body=random.choice(REPLIES),
                        post_number=p + 1,
                        created_at=reply_time,
                    )
                    last_reply_at = reply_time
                    total_posts += 1

                # Cap last_reply_at at 2 hours ago so a live bump always beats seed data
                cap = timezone.now() - datetime.timedelta(hours=2)
                thread.reply_count = n_replies
                thread.last_reply_at = min(last_reply_at, cap)
                thread.save(update_fields=['reply_count', 'last_reply_at'])
                total_threads += 1

        self.stdout.write(self.style.SUCCESS(
            f'✓ {total_threads} threads, {total_posts} posts seeded across {boards.count()} boards'
        ))
