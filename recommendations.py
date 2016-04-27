from math import sqrt
import feedparser
import time
import random
import django
from flask import Flask, request, jsonify, json, render_template
from pydelicious import get_popular, get_userposts, get_urlposts
import pickle

recommendations = Flask(__name__)



criticss={'Daniel Gilljam': {"Toy Story": 5.0, "Deadpool": 3.5, "Star Wars": 5.0, "Avengers": 3.5, "Snake on a plane": 2.5},
         'Kalle Balle': {"Toy Story": 3.0, "Deadpool": 5.0, "Star Wars": 3.0, "Avengers": 3.0, "Snake on a plane": 4.5},
         'Olle Polle': {"Toy Story": 5.0, "Deadpool": 3.0, "Star Wars": 5.0, "Avengers": 3.5, "Snake on a plane": 2.5, "Monsters Inc": 5.0},
         'Chen chin Long': {"Toy Story": 3.5, "Star Trek": 4.5, "Star Wars": 3.5, "Avengers": 4.5, "Snake on a plane": 1.0},
         'Hoo Lee Fuk': {'Toy Story': 3.0, "Star Trek": 5.0, "Star Wars": 5.0, "Avengers": 3.0, "Snake on a plane": 2.5, "Monsters Inc": 1.0},
         'Wai Lee Min': {'Toy Story': 2.5, "Star Wars": 3.5, "Deadpool": 4.5, "Snake on a plane": 4.3, "Monsters Inc": 2.0},
         'Allan Brallan': {"Naruto": 5.0, "Deadpool": 5.0, "Star Wars": 3.5, "Toy Story": 4.5, "Monsters Inc": 4.5}}



#Distans mellan tvp personers smak typ algoritm
def sim_distance(data, person1, person2):


    si={}
    for item in data[person1]:
        if item in data[person2]:
            si[item]=1

    #Om man inte har någon rating gemensamt
    if len(si) == 0:
        return 0

    # Summerar skillnaden mellan personerna upphöjt i 2
    sum_of_squares=sum([pow(data[person1][item]-data[person2][item],2)
                        for item in data[person1] if item in data[person2]])



    return 1/(1+sum_of_squares)



#Pearson correlation Score algoritm
def sim_pearson(data, p1, p2):


    #En dict med gemensamma betygsatta items(filmer)
    si = {}
    for item in data[p1]:
        if item in data[p2]:
            si[item]=1

    #
    n = len(si)

    #Inga betygsättningar i gemenskap
    if n == 0:
        return 0

    #Summerar alla preferenser
    sum1=sum([data[p1][it] for it in si])
    sum2 = sum([data[p2][it] for it in si])

    #Samma emen upphöjt
    sum1Sq = sum([pow(data[p1][it],2) for it in si])
    sum2Sq = sum([pow(data[p2][it],2) for it in si])

    #summera produktena
    pSum = sum([data[p1][it]*data[p2][it] for it in si])

    #Beräknar pearson-score för algoritmen
    num=pSum-(sum1*sum2/n)
    den=sqrt((sum1Sq-pow(sum1,2)/n)*(sum2Sq-pow(sum2,2)/n))
    if den == 0:
        return 0

    r = num/den

    return r


#Kollar likheten mellan två personer mellan 1 till -1. ju närmare 1 ju högre korrelation, ju närmare -1 ju lägre korrelation med den personen
print("Korrelation: ", sim_pearson(criticss, "Daniel Gilljam", "Allan Brallan"))


# Rankar kritikerna(personerna)
def top_matches(data, person, n, similarity=sim_pearson):
    scores = [(similarity(data, person, other), other) for other in data if other !=person]

    scores.sort()
    scores.reverse()
    return scores[:n]


#Få rekommendationer baserad på vad du har gemensqamt med andra
def getRecommendations(data, person, similarity=sim_pearson):
    totals={}
    similiaritySums={}

    for other in data:

        #Jämför inte med dig själv
        if other == person: continue
        sim=similarity(data, person, other)

        #ignorera 0 eller mindre
        if sim<=0:  continue
        for item in data[other]:

            #Bara items(filmer) som jag(personen) inte har sett
            if item not in data[person] or data[person][item] == 0:
                #likheten * score
                totals.setdefault(item, 0)
                totals[item]+=data[other][item]*sim

                #summera alla likheter
                similiaritySums.setdefault(item, 0)
                similiaritySums[item]+=sim



    rankings=[(total/similiaritySums[item], item) for item, total, in totals.items()]

    rankings.sort()
    rankings.reverse()
    return rankings



def transformPrefs(data):
    result={}
    for person in data:
        for item in data[person]:
            result.setdefault(item, {})

            #Flippar personen och items
            result[item][person]=data[person][item]
    return result

#Jämför items med varandra istället för personer, är bättre vid en större data
def calculateSimilarItems(data, n):
    # Create a dict of items showing which other items they are most similar to
    #skapar en dict med items(filmer) som andra items(filmer) som dem har mest gemensamt med
    result = {}

    #Inverterar preferens matricen
    itemData = transformPrefs(data)
    C=0
    for item in itemData:
        #Status update för stora datasets
        C+=1
        if C%100==0:
            print("%d / %d" % (C, len(itemData)))
            #Hitta den som har mest gemensamt med en viss item med sim_distance algoritmen
        scores = top_matches(itemData, item, n=n,similarity=sim_distance)
        result[item] = scores
    return result

def getRecommendedItem(data, itemMatch, user):
    userRating=data[user]
    scores={}
    totalSim={}

    #Loop over items betygsatt av användaren
    for (item, rating) in userRating.items():
        #loop over items liknande denna
        for (similatiry, item2) in itemMatch[item]:
            #Ignorera om den redan betygsatt
            if item2 in userRating:continue

            #Weighted summering av betygsättnigarna och gemenskapen
            scores.setdefault(item2, 0)
            scores[item2]+=similatiry*rating

            #summerin av alla gemenskaper
            totalSim.setdefault(item2, 0)
            totalSim[item2]+=similatiry

    rankings=[(score/totalSim[item], item) for item, score in scores.items()]

    rankings.sort()
    rankings.reverse()
    return rankings


#En negativ korrelation ger en indukation att den personen som gillar filmen nedan troligvis inte gillar den film med en negativ korrelation
# från 1 till -1. Där 1 är att all ratings är samma som en person och -1 är ingen samma. ju närmare 1 ju högre korrelation med den personen ju längre ju sämre korrelation
print("Korrelation mellan top 5 stycken och Daniel Gilljam:", top_matches(criticss, 'Daniel Gilljam', n=5))

#Få rekommendationer på filmer personen inte har sett och ge en estimerad rating.
print("Filmer du bör se dom du inte sett, person-baserad rekommendation: ", getRecommendations(criticss, "Daniel Gilljam"))


# Test av del.is.ous
def initUserDict(tag, n):
    user_dict={}

    #Fåtop count' populära posts
    for p1 in get_popular(tag)[0:n]:
        #Hitta alla användare som postade den
        for p2 in get_urlposts(p1['href']):
            user=p2['user']
            user_dict[user]={}
    return user_dict


def fillItems(user_dict):
    all_items={}
    #Hitta länkar postade av alla användare
    for user in user_dict:
        for i in range(3):
            try:
                posts=get_userposts(user)
                break
            except:
                print("Failed user "+user+", retrying")
                time.sleep(4)
        for post in posts:
            url = post['href']
            user_dict[user][url]=1.0
            all_items[url]=1

    #Fill the missing items with 0
    for ratings in user_dict.values():
        for item in all_items:
            if item not in ratings:
                ratings[item] = 0.0


def loadMovieLens(path='./ml-100k'):
    #Get the movie Titles
    movies={}

    for line in open(path+'/u.item'):
        (id, title)=line.split('|')[0:2]
        movies[id] = title

    #Load the data
    prefs={}

    for line in open(path+'/u.data'):
        (user, movieid, rating, ts) = line.split('\t')
        prefs.setdefault(user,{})
        prefs[user][movies[movieid]]=float(rating)

    return prefs


def search(words, path='./ml-100k'):

    count=0
    found={}
    searchfile = open(path + '/u.item')

    for line in searchfile:
        if words in line:
            (id, title) = line.split('|')[0:2]
            #found.setdefault(title, 0)
            found[id] = title

    searchfile.close()
    return found



prefs = loadMovieLens()

itemsim = calculateSimilarItems(criticss, n=5)
#Item-baserad rekommendation, fungerar bättre än person-baserad rekommenadtion vid större data. Generellt lite bättre.
getRecsNow = getRecommendedItem(criticss, itemsim, 'Daniel Gilljam')
print("Få Rekommendationer på filmer du inte sett men item-baserad rekommendation", getRecsNow)


# Test av MovieLens film data som är laddad in till prefs.
'''
itemsimilarity = calculateSimilarItems(prefs, n=5)
#Få recommendationer baserad på user med userID = 0 i MovieLens filmdatabas, tar längre tid att processera men behöver inte köras så ofta vid större data då det inte ändras så ofta
getRecommends = getRecommendedItem(prefs, itemsimilarity, '0')
print(getRecommends)
'''


'''
pickle.dump(getRecsNow, open("save.p", "wb" ))

@recommendations.route('/')
def index():
    # Filmer som rekommenderas för dig bör printas
    use = pickle.load(open("save.p", "rb" ))
    return jsonify(use)

recommendations.run(debug=True)


'''

#for i in range(len(getRecsNow)):
   # print(getRecsNow[i][1])
