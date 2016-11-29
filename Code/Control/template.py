import requests
import bs4
import importlib

import datetime
from time import mktime

from Utils.message import MessageList
from Utils import utils
from Utils.utils import eprint
from Control.scraper import Scraper

from Model.offer import UnprocessedOffer

from Control import textProcessor as tp # TP tu terror


class Template:
  def __init__(self, job_center, func_filename, url_base, period, area_url, \
               areas_source, num_offSource, links_per_page, num_sources, list_sources, date_feature, first_level_sources):

    self.job_center = job_center
    self.func_filename = func_filename
    self.url_base = url_base
    self.period = period
    self.area_url = area_url
    self.areas_source = areas_source
    self.num_offSource = num_offSource
    self.links_per_page = links_per_page
    self.num_sources = num_sources
    self.list_sources = list_sources
    self.date_feature = date_feature
    self.first_level_sources = first_level_sources

    self.module = None


  @staticmethod
  def read_attributes_from_file(file, main_list):
    """
    Método que obtiene los atributos globales de una plantilla desde un archivo.
    Algunos atributos no están presentes en la plantilla, así que son marcados por
    un valor que determina si son opcionales o no. Si lo son, quedan en None, si no,
    se considera como un error.
    Como este método devuelve None cuando hay errores, en el resto de métodos (llamados por
    execute) considero que si son None, son opcionales
    """
    file.readline() #Global:
      
    job_center, _ = utils.read_text_from_file(file)
    if job_center is None: 
      main_list.add_msg("Failed to read the jobcenter", MessageList.ERR)

    func_filename, _ = utils.read_text_from_file(file)
    if func_filename is None: 
      main_list.add_msg("Failed to read the functions filename", MessageList.ERR)

    url_base, _ = utils.read_url_from_file(file)
    if url_base is None: 
      main_list.add_msg("Failed to read the url Base", MessageList.ERR)

    period, optional = utils.read_text_from_file(file)
    msg_type = MessageList.INF if optional else MessageList.ERR 
    if period is None:
      main_list.add_msg("Failed to read the period", msg_type)

    area_url, optional = utils.read_url_from_file(file)
    msg_type = MessageList.INF if optional else MessageList.ERR
    if area_url is None:
      main_list.add_msg("Failed to read the url to get areas", msg_type)

    areas_source, optional = utils.read_source_from_file(file)
    msg_type = MessageList.INF if optional else MessageList.ERR
    if areas_source is None: 
      main_list.add_msg("Failed to read the source to get areas", msg_type)

    num_offSource, optional = utils.read_source_from_file(file)
    msg_type = MessageList.INF if optional else MessageList.ERR
    if num_offSource is None: 
      main_list.add_msg("Failed to read the source to get the number of offers", msg_type)

    links_per_page, optional = utils.read_int_from_file(file)
    msg_type = MessageList.INF if optional else MessageList.ERR
    if links_per_page is None: 
      main_list.add_msg("Failed to read the number of links per page", msg_type)

    num_sources, _ = utils.read_int_from_file(file)
    if num_sources is None: 
      main_list.add_msg("Failed to read the number of sources to get offers", MessageList.ERR)
    else:
      list_sources = []
      for i in range(0, num_sources):
        offSource, _ = utils.read_source_from_file(file)
        if offSource is None: main_list.add_msg("Failed to read the offer source #" + str(i+1), MessageList.ERR)
        else: list_sources.append(offSource)
    
    # Date feature
    date_feature, optional = utils.read_text_from_file(file)
    if date_feature is None and not optional:
      main_list.add_msg("Failed to read feature from which to extract date", MessageList.ERR)

    # First level features (Front page)
    num_first_features, _ = utils.read_int_from_file(file)
    first_level_sources = []
    for i in range(0, num_first_features):
      msg_list = MessageList()
      features = FeaturesSource.fromFile(file, msg_list)
      if features is None:
        if msg_list.contains_errors():
          msg_list.set_title("Failed to read first level features Source #{num}".format(num=i), MessageList.ERR)
          main_list.add_msg_list(msg_list)
        break
      else:
        first_level_sources.append(features)

    if main_list.contains_errors():
      return None
    else:
      return job_center, func_filename, url_base, period, area_url, areas_source, num_offSource, links_per_page, num_sources, list_sources, date_feature, first_level_sources  



  @classmethod
  def fromFile(cls, file, main_list):
    attributes = cls.read_attributes_from_file(file, main_list)
    if attributes is None:
      return None
    else:
      return cls(*attributes)


  def get_areas(self, main_list):
    """
    Método que obtiene la lista de enlaces a las áreas de las convocatorias
    Devuelve una tupla (areas, optional). Donde:
    areas = Lista de enlaces a las áreas o None
    optional = Indica si no es un error cuando areas es None
    """
    if self.area_url is None:
      main_list.set_title("Not scraping areas: Optional", MessageList.INF)
      return None, True
    
    try:
      web = requests.get(self.area_url)
      soup = bs4.BeautifulSoup(web.text, "lxml")
    except:
      main_list.set_title("Cannot connect: " + self.area_url, MessageList.ERR)
      return None, False
    
    scraper = Scraper(soup, self.areas_source)
    data = scraper.scrape()

    areas = data[0]

    #print(areas)
    #areas = ["medicina-salud"] #Test Aptitus
    #areas = ["/empleos-area-salud-medicina-y-farmacia.html"] #Test Bumeran

    if areas is None:
      main_list.set_title("Failed to scrape areas. Check areas source", MessageList.ERR)
      return None, False
    else:
      main_list.set_title(str(len(areas)) + " Areas obtained", MessageList.INF)
      return areas, False


  def get_num_offers(self, date_url, main_list):
    """
    Obtains number of offers in the specified period
    Returns a tuple (num_offers, optional). Where:
    num_offers = The number of offers or None
    optional = Whether the missing value should be considered an error
    """
    if self.num_offSource is None:
      main_list.set_title("Not scraping number of offers: Optional", MessageList.INF)
      return None, True
    try:
      web = requests.get(date_url)
      soup = bs4.BeautifulSoup(web.text, "lxml")
    except:
      main_list.add_msg("Cannot access the url " + date_url, MessageList.ERR)
      return None, False

    scraper = Scraper(soup, self.num_offSource)
    data = scraper.scrape()
    num_off = data[0]

    try:
      num_off = int(num_off.split()[0])
    except:
      main_list.add_msg("value obtained is not a number", MessageList.ERR)
      num_off = None, False

    if num_off is None:
      main_list.set_title("Fail scraping number of offers.", MessageList.ERR)
      return None, False

    return num_off, False


  def get_offers_from_page_url(self, page_url, main_list, limit=-1):
    try:
      web = requests.get(page_url)
      soup = bs4.BeautifulSoup(web.text, "lxml")
    except Exception as e:
      eprint(e)
      eprint("Cannot access the url: " + page_url + "\n")
      return None


    tot_links = []
    tot_dates = []

    for source in self.list_sources:
      levels = source.split('->')
      index = 0

      scraper = Scraper(soup, source)
      data = scraper.scrape()

      off_links = data[0]
      try:
        dates = data[1]
      except IndexError:
        dates = None

      if off_links is None or type(off_links) is not list or len(off_links) == 0:
        #Useless source
        eprint("No offers obtained using Source: " + source)
        continue

      else:
        #Remember:offLink must be a list

        for index, link in enumerate(off_links):
          if not link in tot_links:
            tot_links.append(link)
            if dates is not None:
              tot_dates.append(dates[index])

    tot_first_features = self.get_first_level_features(soup, len(tot_links))
    
    tot_offers = []
    for index, link in enumerate(tot_links):
      # If limit is negative, it is essentially ignored
      if limit >= 0 and index >= limit:
        break

      eprint("    Offer #" + str(index + 1))
      
      try:
        link_url = self.module.make_link_url(link, page_url)
      except:
        main_list.set_title("make_link_url is not working properly", MessageList.ERR)
        return None

      # Get first level features for this link (offer)
      features = None
      if tot_first_features is not None and len(tot_first_features) > index:
        features = tot_first_features[index]

      offer = self.get_offer_from_link(link_url, features)

      if offer is not None:
        if dates is not None:
          pass_time = tot_dates[index]
        else:
          # If dates is None, attempt to get publication date from self.date_feature
          try:
            pass_time = offer.features[self.date_feature]
          except KeyError:
            main_list.set_title("Can't find '{feature}' field to get publication date".format(feature=self.date_feature), MessageList.ERR)
            return None
        #check!
        try:
          pub_date = self.module.to_publication_date(pass_time)
        except:
          main_list.add_msg("to_publication_date function is not working properly", MessageList.ERR)
          return None

        offer.month = pub_date.month
        offer.year = pub_date.year
      tot_offers.append(offer)

    return tot_offers


  def get_offers_from_period_url(self, period_url, main_list):

    msg_list = MessageList()
    self.num_off, num_off_is_optional = self.get_num_offers(period_url, msg_list)
    main_list.add_msg_list(msg_list)

    if self.num_off is None and not num_off_is_optional:
      return None

    self.num_off = 0 if self.num_off is None else self.num_off
    main_list.add_msg("Número de ofertas encontradas: " + str(self.num_off), MessageList.INF)
    
    max = 2000 if self.links_per_page is not None else 1
    num_pag = 0
    total_offers = []

    while num_pag < max and (len(total_offers) < self.num_off or num_off_is_optional):
      num_pag += 1

      try:
        page_url = self.module.make_page_url(num_pag, period_url)
      except:
        main_list.set_title("make_page_url is not working properly", MessageList.ERR)
        #Abort everything
        return None #Return total_offers if you dont wanna abort all

      eprint("  Page #" + str(num_pag))
      offers = self.get_offers_from_page_url(page_url, main_list)
      eprint("")

      if offers is None:
        #Error page
        break
      else:
        total_offers += offers
        if len(offers) != self.links_per_page and len(total_offers) != self.num_off:
          main_list.add_msg("Unexpected number of offers at page #" + str(num_pag), MessageList.INF)

    main_list.set_title(str(len(total_offers)) + " offers obtained in total (Invalid included)", MessageList.INF)
    return total_offers
  
  def get_offers_from_area_url(self, area_url, main_list):
    try:
      period_url = self.module.make_period_url(self.period, area_url)
    except:
      main_list.set_title("make_period_url function is not working propertly", MessageList.ERR)
      return None

    msg_list = MessageList()
    offers = self.get_offers_from_period_url(period_url, msg_list)
    main_list.add_msg_list(msg_list)

    if offers is None:
      main_list.set_title("No se pudo obtener las ofertas", MessageList.ERR)
      return None

    else:
      valid_offers = []
      for offer in offers:
        if offer is not None:
          valid_offers.append(offer)

      main_list.set_title(str(len(valid_offers))+ " ofertas validas seleccionadas", MessageList.INF)
      return valid_offers


  def execute(self, main_list):

    print(self.job_center)
    UnprocessedOffer.connectToDatabase(self.job_center)

    #Importing Custom Functions
    msg_list = MessageList()
    mod = custom_import(self.func_filename, msg_list)
    main_list.add_msg_list(msg_list)

    if mod is not None:
      self.module = mod

      msg_list = MessageList()
      areas, optional = self.get_areas(msg_list)
      main_list.add_msg_list(msg_list)

      if areas is not None or optional:
        try:
          urls = self.module.make_area_urls(areas, self.url_base)
          area_urls = list(urls)
        except:
          main_list.add_msg("La funcion make_area_urls no esta funcionando correctamente", MessageList.ERR)
          main_list.set_title("La plantilla falló al ejecutarse" + self.job_center, MessageList.ERR)
          return None

        for index, area_url in enumerate(area_urls):
          
          main_list.add_msg("Area #"+str(index+1), MessageList.INF)
          main_list.add_msg(area_url, MessageList.INF)
          msg_list = MessageList()
          eprint("Area #"+str(index+1)+"   "+area_url)
          offers = self.get_offers_from_area_url(area_url, msg_list)
          eprint("------------------------------------------------------------------------------")
          main_list.add_msg_list(msg_list)

          if offers is not None:
            msg_list = MessageList()
            load_offers(offers, msg_list)
            main_list.add_msg_list(msg_list)

        main_list.set_title("La plantilla " + self.job_center + " se ejecutó correctamente.", MessageList.INF)
        return 

    main_list.set_title("La plantilla " + self.job_center + " falló al ejecutarse", MessageList.ERR)
    
  def get_first_level_features(self, soup, num_offers):
    """
    Method that gets all first level features to later add them to each offer
    """
    tot_first_features = [{} for i in range(0, num_offers)]
    for source in self.first_level_sources:
      names = self.get_data_from_source(soup, source.names_source)
      # Values is either a list of features (one for each offer)
      # or just one feature to assign to all the offers
      values = self.get_data_from_source(soup, source.values_source)
      print("Names: ", names)
      print("Values: ", values)
      
      for index, features in enumerate(tot_first_features):
        for name in names:
          value = values if type(values) is not list else values[index]
          features[name] = value

    return tot_first_features



def load_offers(offers, main_list):
  error_loading = False
  cnt_load = 0
  cnt_disc = 0
  cnt_err = 0

  for offer in offers:
    inserted = offer.insert()
    if inserted is None:
      cnt_err += 1
      error_loading = True
    else:
      if inserted:
        cnt_load += 1
      else:
        cnt_disc += 1

  main_list.add_msg(str(cnt_load)+ " Offers succesfully loaded to database", MessageList.INF)
  main_list.add_msg(str(cnt_disc)+ " Offers discarted because of duplication in database", MessageList.INF)
  main_list.add_msg(str(cnt_err) + " Offers failed to load to database", MessageList.ERR)

  if error_loading:
    main_list.set_title("Some offers couldn't be loaded. Check detail file", MessageList.ERR)
  else:
    main_list.set_title("All offers were loaded", MessageList.INF)



def custom_import(filename, main_list):

  mod_name = "Functions." + filename

  try:
    mod = importlib.import_module(mod_name)
  except Exception as e:
    main_list.add_msg(str(e), MessageList.ERR)
    main_list.set_title("Incorrect function module filename", MessageList.ERR)
    return None

  #Check function existence
  custom_functions = dir(mod)

  if not "make_area_urls" in custom_functions:
    main_list.add_msg("Missing make_area_urls function", MessageList.ERR)

  if not "make_period_url" in custom_functions:
    main_list.add_msg("Missing make_period_url function", MessageList.ERR)

  if not "make_page_url" in custom_functions:
    main_list.add_msg("Missing make_page_url function", MessageList.ERR)

  if not "make_link_url" in custom_functions:
    main_list.add_msg("Missing make_link_url function", MessageList.ERR)

  if not "to_publication_date" in custom_functions:
    main_list.add_msg("Missing to_publication_date function", MessageList.ERR)

  if main_list.contains_errors():
    main_list.set_title("Fail importing function file", MessageList.ERR)
    return None
  else:
    main_list.set_title("Function file imported", MessageList.INF)
    return mod 




#------------------------------------------------------------------------------------------------
class FeaturesSource:
  def __init__(self, names_source, values_source):
    self.names_source = names_source
    self.values_source = values_source


  @classmethod
  def fromFile(cls, file, main_list):
    fileline, _ = utils.read_text_from_file(file)
    if fileline is None or utils.is_blank(fileline) :
      return None
      
    names = utils.read_source_from_string(fileline, main_list)
    if names is None:
      main_list.add_msg("Failed to read names", MessageList.ERR)
    values, _ = utils.read_source_from_file(file)
    if values is None:
      main_list.add_msg("Failed to read values", MessageList.ERR)

    if main_list.contains_errors():
      return None
    else:
      return cls(names, values)






#------------------------------------------------------------------------------------------------
class OfferTemplate(Template):

  def __init__(self, global_attributes, id_features, feat_sources):

    Template.__init__(self, *global_attributes)
    self.id_features = id_features
    self.feat_sources = feat_sources
  

  @staticmethod
  def read_attributes_from_file(file, main_list):
    global_attr = Template.read_attributes_from_file(file, main_list)
    file.readline() #newline
    file.readline() #Offer Structure:

    id_features, _ = utils.read_source_from_file(file)
    id_feat = []
    for feature in id_features:
        id_feat.append(feature.lower())

    id_features = id_feat
    
    # Back features (Full posting)
    features_sources = []
    while True:
      msg_list = MessageList()
      features_source = FeaturesSource.fromFile(file, msg_list)
    
      if features_source is None:
        if msg_list.contains_errors():
          msg_list.set_title("Failed to read features Source #" + str(len(features_sources)+1), MessageList.ERR)
          main_list.add_msg_list(msg_list)

        break
      else:
        features_sources.append(features_source)

    if not main_list.contains_errors():
      main_list.set_title("All Offer Template Attributes are OK :)", MessageList.INF)
      return global_attr, id_features, features_sources
    else:
      main_list.set_title("Some Offer Template Attributes are WRONG :(", MessageList.ERR)
      return None



  def get_data_from_source(self, soup, source):
    if source == "":
      return None

    if (type(source) is list):
      return source

    scraper = Scraper(soup, source)
    data = scraper.scrape()[0]
    return data


  def get_offer_from_link(self, link, first_level_features):
    try:
      web = requests.get(link)
      soup = bs4.BeautifulSoup(web.text, "lxml")
    except:
      eprint("Cannot access to the link "+link)
      return None

    # Back Features (Full posting)
    features = {}
    for feat_source in self.feat_sources:
      names = self.get_data_from_source(soup, feat_source.names_source)
      values = self.get_data_from_source(soup, feat_source.values_source)
      print("Names: ", names)
      print("Values: ", values)

      for idx in range(min(len(names), len(values))):
        features[names[idx].lower()] = values[idx]
    
    # Merge features dictionaries
    for key, value in first_level_features.items():
      features[key] = value

    #Get id
    id = ""
    for id_feat in self.id_features:
      try:
        id += features[id_feat] + ' '
      except:
        id += ' '
        #Hardcoding!!!!
        if id_feat == "descripción":
            eprint("    Descripción vacía. Oferta INVÁLIDA")
            eprint("    Link: ", link)
            return None

    id = tp.preprocess(id)
    if id =="": 
      eprint("    ID vacío. Oferta INVÁLIDA")
      eprint("    Link: ", link)
      return None
    else:
      offer = UnprocessedOffer(0, 0, id, True, 0, features)
      return offer